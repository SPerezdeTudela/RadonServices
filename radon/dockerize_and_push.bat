ECHO "Copying library files..."
cd ..
robocopy ./commons/ ./radon/src/commons/ /MIR
cd ./radon

ECHO "Building image..."
docker build --no-cache -t dockerneoc/radon:pipeline-radon .

ECHO "Cleaning up build files..."
rmdir /s /q "./src/commons"

ECHO "Publishing to docker hub..."
docker push dockerneoc/radon:pipeline-radon

ECHO "Complete!"
