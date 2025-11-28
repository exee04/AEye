import numpy as np

class FingerStabilizer:
    def __init__(self):
        self.history = []              # last 5 world positions
        self.max_hist = 5

        # 1D Kalman filter for X,Y,Z
        self.x = np.zeros((3,1))
        self.P = np.eye(3) * 1.0
        self.Q = np.eye(3) * 0.0001    # low motion noise
        self.R = np.eye(3) * 0.01      # moderate measurement noise
        self.initialized = False

        # EMA smooth
        self.ema = None
        self.alpha = 0.10   # B = balanced

    def update(self, xyz):
        xyz = np.array(xyz).reshape(3,1)

        # -----------------------------
        # 1. KEEP LAST 5 SAMPLES
        # -----------------------------
        self.history.append(xyz)
        if len(self.history) > self.max_hist:
            self.history.pop(0)

        # median filter
        hist_stack = np.hstack(self.history)
        med = np.median(hist_stack, axis=1).reshape(3,1)

        # -----------------------------
        # 2. KALMAN FILTER (X,Y,Z)
        # -----------------------------
        if not self.initialized:
            self.x = med.copy()
            self.initialized = True
        else:
            # predict
            self.P = self.P + self.Q

            # update
            y = med - self.x
            S = self.P + self.R
            K = self.P @ np.linalg.inv(S)

            self.x = self.x + K @ y
            self.P = (np.eye(3) - K) @ self.P

        kf_out = self.x.copy()

        # -----------------------------
        # 3. EMA FINAL SMOOTH
        # -----------------------------
        if self.ema is None:
            self.ema = kf_out.copy()
        else:
            self.ema = self.alpha * kf_out + (1 - self.alpha) * self.ema

        return self.ema.reshape(3)

