FROM python:3.12-slim
RUN pip install --no-cache-dir mujoco numpy
WORKDIR /bench
COPY run_all.py tick_loop.py tracked_avatar.xml ./
CMD ["python3", "run_all.py"]
