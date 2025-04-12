# A.Eye  
A.Eye is an intelligent visual recognition system running on the Raspberry Pi 5 (RPi5), designed to assist in Braille detection and accessibility enhancement using computer vision.

---

## 📌 Overview  
A.Eye leverages advanced object detection models, including YOLOv8 by Ultralytics, to identify and process Braille characters from captured images. The system is built for efficiency and portability, taking advantage of the Raspberry Pi 5's capabilities and camera integration.

---

## 📸 Hardware Requirements
- Raspberry Pi 5
- Camera Module (compatible with Picamera2)
- 128GB MicroSD card with Raspberry Pi OS
- Optional: Display module for visual output

---

## 📈 Dataset
We used an open-source Braille detection dataset provided via Roboflow Universe. It is freely available and supports model training and evaluation for Braille character detection.

**Link**: [Braille Detection Dataset on Roboflow](https://universe.roboflow.com/braille-lq5eh/braille-detection)

---

## 🔒 License Info
This project includes tools and references licensed under AGPL-3.0 via YOLOv8. Ensure compliance with its requirements for derivative or redistributable work. Refer to Ultralytics' official license for details.

---

## 📚 Citations
You can include these citations in your academic or research publications:

<details>
<summary><strong>Ultralytics YOLOv8</strong></summary>

```bibtex
@software{yolov8_ultralytics,
  author = {Glenn Jocher and Ayush Chaurasia and Jing Qiu},
  title = {Ultralytics YOLOv8},
  version = {8.0.0},
  year = {2023},
  url = {https://github.com/ultralytics/ultralytics},
  orcid = {0000-0001-5950-6979, 0000-0002-7603-6750, 0000-0003-3783-7069},
  license = {AGPL-3.0}
}
```
</details>

<details>
<summary><strong>Braille Detection Dataset</strong></summary>

```bibtex
@misc{braille-detection_dataset,
  title = {Braille Detection Dataset},
  type = {Open Source Dataset},
  author = {Braille},
  howpublished = {\\url{https://universe.roboflow.com/braille-lq5eh/braille-detection}},
  url = {https://universe.roboflow.com/braille-lq5eh/braille-detection},
  journal = {Roboflow Universe},
  year = {2023},
  month = {apr},
  note = {visited on 2025-04-13}
}
```
</details>

---

## 🤝 Acknowledgements
- [Ultralytics](https://github.com/ultralytics/ultralytics) for YOLOv8
- [Roboflow](https://universe.roboflow.com) for dataset tools and hosting

---
