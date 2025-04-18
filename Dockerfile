FROM python:3.9-alpine

# update apk repo
RUN echo "http://dl-4.alpinelinux.org/alpine/v3.10/main" >> /etc/apk/repositories && \
    echo "http://dl-4.alpinelinux.org/alpine/v3.10/community" >> /etc/apk/repositories

# install chromedriver
RUN apk update
RUN apk add chromium chromium-chromedriver
ENV CHROME_BIN=/usr/bin/chromium-browser \
    CHROME_PATH=/usr/lib/chromium/

COPY . /usr/local/bin/
COPY . .

# install python libraries
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# entrypoint
ENV DISPLAY=:99

RUN python download_chrome.py

ENTRYPOINT [ "python" ,  "-u" , "app.py" ] 