FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3-pip && pip install pygments requests twine boto3
RUN useradd -ms /bin/bash runuser
USER runuser
WORKDIR /app
CMD ["bash"]
