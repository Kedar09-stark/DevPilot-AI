
# --------------------------------------------------
# Stage 1: Build the React Frontend
# --------------------------------------------------

# Use Node.js 22 to build the Vite application.
FROM node:22-alpine AS builder

# Set the working directory.
WORKDIR /app

# Copy package manifests first for better Docker caching.
COPY package*.json ./

# Install exact dependencies from package-lock.json.
RUN npm ci

# Copy the frontend source code.
COPY . .

# Build the production frontend.
RUN npm run build


# --------------------------------------------------
# Stage 2: Serve Frontend Using Nginx
# --------------------------------------------------

# Use a lightweight Nginx image.
FROM nginx:alpine

# Remove the default Nginx website configuration.
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom Nginx configuration.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the production frontend files from the builder stage.
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose the HTTP port.
EXPOSE 80

# Start Nginx in the foreground.
CMD ["nginx", "-g", "daemon off;"]
