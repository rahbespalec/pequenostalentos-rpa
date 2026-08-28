FROM docker:27-cli
RUN apk add --no-cache python3 py3-pip
WORKDIR /runner
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY server.py .
COPY job /job
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["/runner/entrypoint.sh"]
