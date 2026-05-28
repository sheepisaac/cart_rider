# CART RIDER: Classification And Real-time sTReamIng Detection-Enabled Rover
This repository is about playing openCV-Yolo-UART signalling-based online streaming racing game code (cart_rider NOT kart_rider)

# Cart Rider Run Commands

## Basic Run

```bash
cd ~/cart_rider
./run_cart_rider
```

Open the URL printed in the terminal from your browser.

```text
http://<cart IP>:8080/
```

Use Enter to move through the title screens. On the streaming option screen, type `1`, `2`, or `3`, then press Enter.

## Streaming Options

```text
1: only streaming
2: opencv-only detection streaming
3: object detection streaming w/ YOLO
```

## Run With a YOLO Model

To specify a YOLO `.pt` model file directly:

```bash
cd ~/cart_rider
CART_RIDER_YOLO_WEIGHTS=/home/cartrider/yolov5/yolov5n.pt ./run_cart_rider
```

If your model is in a different location, replace only the `CART_RIDER_YOLO_WEIGHTS` value.

```bash
CART_RIDER_YOLO_WEIGHTS=/path/to/model.pt ./run_cart_rider
```

## YOLO Latency Tuning

Lower latency preference:

```bash
cd ~/cart_rider
CART_RIDER_YOLO_WEIGHTS=/home/cartrider/yolov5/yolov5n.pt CART_RIDER_YOLO_IMGSZ=224 CART_RIDER_YOLO_EVERY_N=4 ./run_cart_rider
```

Higher accuracy preference:

```bash
cd ~/cart_rider
CART_RIDER_YOLO_WEIGHTS=/home/cartrider/yolov5/yolov5n.pt CART_RIDER_YOLO_IMGSZ=320 CART_RIDER_YOLO_EVERY_N=3 ./run_cart_rider
```

Current defaults:

```bash
CART_RIDER_YOLO_IMGSZ=256
CART_RIDER_YOLO_EVERY_N=3
CART_RIDER_YOLO_TORCH_THREADS=2
```

## Browser Controls

Click the streaming page once, then use the keyboard controls below.

```text
w: go forward
a: left forward
d: right forward
s: go backward
z: left backward
c: right backward
b: BOOST!
q: quit game
Backspace: previous page
```

## YOLO venv Dependency Notes

To install the remaining packages in the YOLOv5 virtual environment:

```bash
cd ~/yolov5
source yolov5/bin/activate
pip install pandas pyyaml requests scipy tqdm packaging psutil thop ultralytics seaborn
```

If `torch` and `torchvision` are already installed, you do not need to install them again.
