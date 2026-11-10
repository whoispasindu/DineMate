FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    YOLO_CONFIG_DIR=/home/vision/.config/Ultralytics

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 torchvision==0.29.2 \
    && pip install ultralytics==8.4.177 lap==0.5.14 httpx==0.28.1 numpy==2.5.4 yt-dlp==2026.10.26 \
        opencv-python-headless==5.0.0.93 \
    && pip uninstall -y opencv-python \
    && pip install --force-reinstall --no-deps opencv-python-headless==5.0.0.93

RUN useradd --create-home --uid 10001 vision

WORKDIR /app
COPY --chown=vision:vision . .
RUN mkdir -p models "$YOLO_CONFIG_DIR" \
    && chown -R vision:vision models /home/vision

USER vision

RUN python -c "from ultralytics import YOLO; YOLO('models/yolo11s.pt'); YOLO('models/yolo11s-pose.pt')"

EXPOSE 8090-8097

CMD ["python", "-m", "vision.hub"]
