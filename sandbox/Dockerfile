FROM ubuntu:22.04
RUN apt-get update && apt-get install -y python3 python3-pip curl git xdotool scrot && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY . /work
RUN pip3 install -r requirements.txt || true
CMD ["bash"]
