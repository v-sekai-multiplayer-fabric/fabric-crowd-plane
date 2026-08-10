# A room: one crowd plane, publishing fabric packets. No renderer, no browser.
FROM python:3.12-slim
RUN pip install --no-cache-dir mujoco numpy websockets zstandard
WORKDIR /room
COPY proto/plane.py proto/entity_packet.py proto/interest.py proto/handoff.py ./proto/
COPY bench/touchable.py ./bench/
COPY assets/tracked_avatar.xml ./assets/
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/room
EXPOSE 8770
CMD ["python3", "proto/plane.py"]
