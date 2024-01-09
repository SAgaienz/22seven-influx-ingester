FROM --platform=linux/amd64 python:3.9-buster

RUN apt-get update && apt-get install -y gnupg2
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub |  apt-key add - 
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'

# Install Chrome
RUN apt-get update
RUN apt-get install -y google-chrome-stable

ENV DISPLAY=:99

COPY . /usr/local/bin/
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN python download_chrome.py

ENTRYPOINT [ "python" ,  "-u" , "app.py" ] 