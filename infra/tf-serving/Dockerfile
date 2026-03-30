FROM tensorflow/serving:2.15.0

# Copy the exported SavedModel directory into the serving container's path.
# The expected structure is: /models/nba_wide_deep/1/saved_model.pb
COPY ./saved_model /models/nba_wide_deep/1

# Set the model name environment variable so TF Serving knows which model to host
ENV MODEL_NAME=nba_wide_deep
ENV PORT=8501

# Start the TensorFlow Serving REST API
CMD ["tensorflow_model_server", "--port=8500", "--rest_api_port=8501", "--model_name=${MODEL_NAME}", "--model_base_path=/models/${MODEL_NAME}"]

# EXPOSED PORTS:
# 8500: gRPC port
# 8501: REST API port
