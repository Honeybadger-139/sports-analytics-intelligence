"""
Vertex AI Endpoint Deployment Script

This script takes the local TensorFlow "SavedModel" artifact, uploads it to 
Google Cloud Storage (GCS), registers it in the Vertex AI Model Registry, 
and deploys it to a Vertex AI Endpoint for scalable, decoupled inference.

Usage:
  python scripts/deploy_vertex_endpoint.py --model-dir models/nba_wide_deep --endpoint-name GameThreadInference
"""

import sys
import logging
try:
    from google.cloud import aiplatform
except ImportError:
    print("Please install google-cloud-aiplatform: pip install google-cloud-aiplatform")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)

def deploy_to_vertex(project_id: str, location: str, gcs_artifact_uri: str, display_name: str):
    logging.info(f"Initializing Vertex AI SDK for project {project_id} in {location}...")
    aiplatform.init(project=project_id, location=location)

    logging.info(f"Uploading model to Vertex AI Registry from {gcs_artifact_uri}...")
    # Use the pre-built TensorFlow serving container provided by Google
    serving_image_uri = f"{location}-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-15:latest"

    model = aiplatform.Model.upload(
        display_name=display_name,
        artifact_uri=gcs_artifact_uri,
        serving_container_image_uri=serving_image_uri,
        description="TensorFlow Wide & Deep model for NBA predictions"
    )
    
    logging.info(f"Model uploaded successfully. Creating Endpoint...")
    endpoint = aiplatform.Endpoint.create(display_name=f"{display_name}_endpoint")

    logging.info(f"Deploying Model to Endpoint: {endpoint.resource_name}...")
    # Here we decouple the API from inference: we deploy the model on dedicated n1-standard-2 machines
    model.deploy(
        endpoint=endpoint,
        machine_type="n1-standard-2",
        min_replica_count=1,
        max_replica_count=3,
        sync=True
    )
    
    logging.info("🔥 Deployment complete!")
    logging.info(f"Endpoint ID needed for backend/.env: {endpoint.name}")
    logging.info(f"Test via REST or the python SDK: endpoint.predict(instances=[...])")

if __name__ == "__main__":
    print("This script is a blueprint. Please set your GCP_PROJECT, GCS bucket, and run manually.")
