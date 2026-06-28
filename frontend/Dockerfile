FROM nginx:1.25-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template

# Use envsubst to substitute only BACKEND_HOST, leaving nginx variables intact
CMD ["/bin/sh", "-c", \
    "envsubst '${BACKEND_HOST}' < /etc/nginx/conf.d/default.conf.template \
     > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]

EXPOSE 80
