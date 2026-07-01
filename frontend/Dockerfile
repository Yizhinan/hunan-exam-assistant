FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
# Use npmmirror in China
RUN npm config set registry https://registry.npmmirror.com && npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
