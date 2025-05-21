FROM python:3.12-alpine

ENV PYTHONUNBUFFERED=1

# Install Ecowitt Exporter
COPY requirements.txt /
RUN pip install -r /requirements.txt
COPY ecowitt_exporter.py conversions.py /
WORKDIR /

# Run it!
CMD ["python", "ecowitt_exporter.py"]
EXPOSE 8088/tcp
