import cv2
import numpy as np
import json
import os
from math import sqrt

# helpers for quaternion conversions (small, dependency-free)
def rotmat_to_quat(R):
    """Convert 3x3 rotation matrix to quaternion [w, x, y, z]."""
    # Method robust to numerical issues
    m = R
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = 0.5 / np.sqrt(t + 1.0)
        w = 0.25 / s
        x = (m[2, 1] - m[1, 2]) * s
        y = (m[0, 2] - m[2, 0]) * s
        z = (m[1, 0] - m[0, 1]) * s
    else:
        if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
            s = 2.0 * np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
            w = (m[2, 1] - m[1, 2]) / s
            x = 0.25 * s
            y = (m[0, 1] + m[1, 0]) / s
            z = (m[0, 2] + m[2, 0]) / s
        elif m[1, 1] > m[2, 2]:
            s = 2.0 * np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
            w = (m[0, 2] - m[2, 0]) / s
            x = (m[0, 1] + m[1, 0]) / s
            y = 0.25 * s
            z = (m[1, 2] + m[2, 1]) / s
        else:
            s = 2.0 * np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
            w = (m[1, 0] - m[0, 1]) / s
            x = (m[0, 2] + m[2, 0]) / s
            y = (m[1, 2] + m[2, 1]) / s
            z = 0.25 * s
    q = np.array([w, x, y, z], dtype=np.float64)
    q /= np.linalg.norm(q)
    return q

def quat_to_rotmat(q):
    """Convert quaternion [w,x,y,z] to 3x3 rotation matrix."""
    w, x, y, z = q
    # normalize
    n = np.linalg.norm(q)
    if n == 0:
        return np.eye(3, dtype=np.float64)
    w, x, y, z = q / n
    R = np.array([
        [1 - 2*(y*y + z*z),     2*(x*y - z*w),       2*(x*z + y*w)],
        [2*(x*y + z*w),         1 - 2*(x*x + z*z),   2*(y*z - x*w)],
        [2*(x*z - y*w),         2*(y*z + x*w),       1 - 2*(x*x + y*y)]
    ], dtype=np.float64)
    return R

def slerp_quat(q1, q2, t):
    """Spherical linear interpolation (approx) - fallback to lerp for tiny angles"""
    # ensure unit quaternions
    q1 = q1 / np.linalg.norm(q1)
    q2 = q2 / np.linalg.norm(q2)
    dot = np.dot(q1, q2)
    if dot < 0.0:
        q2 = -q2
        dot = -dot
    DOT_THRESHOLD = 0.9995
    if dot > DOT_THRESHOLD:
        # linear interpolation then normalize
        result = q1 + t*(q2 - q1)
        return result / np.linalg.norm(result)
    theta_0 = np.arccos(dot)
    theta = theta_0 * t
    q3 = q2 - q1*dot
    q3 /= np.linalg.norm(q3)
    return q1*np.cos(theta) + q3*np.sin(theta)


class BrailleOverlayHandler:
    def __init__(self, camera_matrix=None, dist_coeffs=None, marker_size_m=0.0254, ref_res=(640,480)):
        """
        camera_matrix: 3x3 numpy array (if None, must be provided later)
        dist_coeffs: distortion (if None -> zeros)
        marker_size_m: marker physical size in meters (1 inch -> 0.0254m)
        """
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs if dist_coeffs is not None else np.zeros((5,1), dtype=np.float32)
        self.marker_size = float(marker_size_m)
        self.ref_res = ref_res

        # braille positions are expected in millimetres in JSON: { "label":"A", "relative":[x_mm,y_mm], "size":[w_mm,h_mm] }
        self.braille_positions = []

        # pose state
        self._rvec = None         # raw last rvec (3x1)
        self._tvec = None         # raw last tvec (3x1)
        self._quat = None         # smoothed quaternion
        self._tvec_filt = None    # smoothed translation
        self._pose_initialized = False

        # smoothing params
        self.trans_alpha = 0.6    # EMA alpha for translation (0..1) higher => keep old more (smoother slower)
        self.rot_interp_t = 0.45  # blending factor for quaternion towards new (0..1)
        self.max_translation_jump_m = 0.06  # reject frames with translation jump > 6cm (tune)
        self.hovered_label = None
        self.mode = "offline"

    # -----------------------------
    # Load braille JSON (keep mm units)
    # -----------------------------
    def load_braille_layout(self, path):
        if not os.path.exists(path):
            print(f"[BrailleOverlay] Layout not found: {path}")
            self.braille_positions = []
            return
        with open(path, "r") as f:
            data = json.load(f)
        self.braille_positions = data.get("braille_positions", [])
        print(f"[BrailleOverlay] Loaded {len(self.braille_positions)} braille positions (mm units expected).")

    # -----------------------------
    # Replace or set camera intrinsics (call early)
    # -----------------------------
    def set_camera_intrinsics(self, cam_w, cam_h, fov_deg=120.0):
        # approximate focal length from FOV if camera_matrix not provided
        if self.camera_matrix is None:
            fov = float(fov_deg) * np.pi / 180.0
            fx = (cam_w / 2.0) / np.tan(fov / 2.0)
            fy = fx
            cx = cam_w / 2.0
            cy = cam_h / 2.0
            self.camera_matrix = np.array([[fx, 0, cx],[0, fy, cy],[0,0,1]], dtype=np.float32)
            print(f"[BrailleOverlay] Generated intrinsics fx={fx:.1f}, cx={cx}, cy={cy}")

    # -----------------------------
    # Pose smoothing + update
    # rvec (3,1) and tvec (3,1) are outputs from solvePnP (radians + meters)
    # we convert rotation -> quat and blend, translation uses EMA with outlier rejection
    # -----------------------------
    def update_pose_filtered(self, rvec, tvec):
        # convert arrays to np.float64
        rvec = np.asarray(rvec, dtype=np.float64).reshape(3)
        tvec = np.asarray(tvec, dtype=np.float64).reshape(3)

        # convert rvec -> rotation matrix -> quaternion
        R, _ = cv2.Rodrigues(rvec)
        q_new = rotmat_to_quat(R)

        if not self._pose_initialized:
            # initialize filters
            self._quat = q_new
            self._tvec_filt = tvec.copy()
            self._rvec = rvec.copy()
            self._tvec = tvec.copy()
            self._pose_initialized = True
            return

        # outlier rejection on translation magnitude jump
        jump = np.linalg.norm(tvec - self._tvec)
        if jump > self.max_translation_jump_m:
            # ignore this frame's translation and rotation (but do not discard entirely)
            # instead, slightly nudge toward the new pose with a very small factor
            tiny = 0.05
            self._tvec_filt = (1 - tiny) * self._tvec_filt + tiny * tvec
            self._quat = slerp_quat(self._quat, q_new, tiny)
            self._tvec = tvec.copy()
            return

        # translation EMA
        alpha = self.trans_alpha
        self._tvec_filt = alpha * self._tvec_filt + (1.0 - alpha) * tvec
        self._tvec = tvec.copy()

        # quaternion interpolate (slerp/lerp mix)
        t = self.rot_interp_t
        self._quat = slerp_quat(self._quat, q_new, t)
        # update stored rvec from quat for backwards compatibility when needed
        R_smooth = quat_to_rotmat(self._quat)
        rvec_sm, _ = cv2.Rodrigues(R_smooth)
        self._rvec = rvec_sm.reshape(3)

    # -----------------------------
    # Directly set pose (useful when you want to bypass filtering)
    # -----------------------------
    def set_pose_direct(self, rvec, tvec):
        self._rvec = np.asarray(rvec, dtype=np.float64).reshape(3)
        self._tvec = np.asarray(tvec, dtype=np.float64).reshape(3)
        R, _ = cv2.Rodrigues(self._rvec)
        self._quat = rotmat_to_quat(R)
        self._tvec_filt = self._tvec.copy()
        self._pose_initialized = True

    # -----------------------------
    # Draw overlay: projects each braille mm -> meters -> image px using filtered pose
    # -----------------------------
    def draw(self, frame):
        if not self.braille_positions or not self._pose_initialized or self.camera_matrix is None:
            return frame

        rvec = self._rvec.reshape(3, 1).astype(np.float32)
        tvec = self._tvec_filt.reshape(3, 1).astype(np.float32)

        for b in self.braille_positions:
            rel_x_mm, rel_y_mm = b["relative"]
            label = b.get("label", "?")
            size_w_mm, size_h_mm = b.get("size", [10, 10])

            # center point in marker coordinates (meters). Note Y inverted to match original convention.
            pt3 = np.array([[rel_x_mm / 1000.0, -rel_y_mm / 1000.0, 0.0]], dtype=np.float32)

            proj, _ = cv2.projectPoints(pt3, rvec, tvec, self.camera_matrix, self.dist_coeffs)
            px_x, px_y = float(proj[0,0,0]), float(proj[0,0,1])

            # project a corner to estimate pixel half-size
            corner3 = np.array([[(rel_x_mm + size_w_mm/2.0) / 1000.0, -(rel_y_mm + size_h_mm/2.0) / 1000.0, 0.0]], dtype=np.float32)
            proj_c, _ = cv2.projectPoints(corner3, rvec, tvec, self.camera_matrix, self.dist_coeffs)
            cx, cy = float(proj_c[0,0,0]), float(proj_c[0,0,1])

            half_w_px = abs(cx - px_x)
            half_h_px = abs(cy - px_y)
            # clamp minimal sizes to keep visible
            half_w_px = max(half_w_px, 8)
            half_h_px = max(half_h_px, 8)

            top_left = (int(px_x - half_w_px), int(px_y - half_h_px))
            bottom_right = (int(px_x + half_w_px), int(px_y + half_h_px))

            color = (0, 255, 0) if label != self.hovered_label else (0, 0, 255)
            cv2.rectangle(frame, top_left, bottom_right, color, 2)
            cv2.putText(frame, str(label), (top_left[0], top_left[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return frame

    # -----------------------------
    # Mouse hover detection using projection (accurate)
    # -----------------------------
    def on_mouse_move(self, event, x, y, flags, param):
        if event != cv2.EVENT_MOUSEMOVE or not self._pose_initialized or self.camera_matrix is None:
            return

        found = None
        rvec = self._rvec.reshape(3, 1).astype(np.float32)
        tvec = self._tvec_filt.reshape(3, 1).astype(np.float32)

        for b in self.braille_positions:
            rel_x_mm, rel_y_mm = b["relative"]
            size_w_mm, size_h_mm = b["size"]

            pt3 = np.array([[rel_x_mm / 1000.0, -rel_y_mm / 1000.0, 0.0]], dtype=np.float32)
            proj, _ = cv2.projectPoints(pt3, rvec, tvec, self.camera_matrix, self.dist_coeffs)
            px_x, px_y = float(proj[0,0,0]), float(proj[0,0,1])

            corner3 = np.array([[(rel_x_mm + size_w_mm/2.0) / 1000.0, -(rel_y_mm + size_h_mm/2.0) / 1000.0, 0.0]], dtype=np.float32)
            proj_c, _ = cv2.projectPoints(corner3, rvec, tvec, self.camera_matrix, self.dist_coeffs)
            cx, cy = float(proj_c[0,0,0]), float(proj_c[0,0,1])

            half_w = abs(cx - px_x)
            half_h = abs(cy - px_y)
            if (px_x - half_w) <= x <= (px_x + half_w) and (px_y - half_h) <= y <= (px_y + half_h):
                found = b.get("label", "?")
                break

        if found != self.hovered_label:
            self.hovered_label = found
            if found:
                print("[Hover]", found)

    # -----------------------------
    # Convenience: set smoothing params at runtime
    # -----------------------------
    def set_smoothing(self, trans_alpha=None, rot_interp_t=None, max_jump=None):
        if trans_alpha is not None:
            self.trans_alpha = float(trans_alpha)
        if rot_interp_t is not None:
            self.rot_interp_t = float(rot_interp_t)
        if max_jump is not None:
            self.max_translation_jump_m = float(max_jump)

