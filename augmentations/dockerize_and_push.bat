ECHO "Copying library files..."
cd ..
robocopy ./commons/ ./augmentations/src/commons/ /MIR
cd ./augmentations

ECHO "Building image..."
docker build --no-cache -t dockerneoc/radon:pipeline-augment .

ECHO "Cleaning up build files..."
rmdir /s /q "./src/commons"

ECHO "Publishing to docker hub..."
docker push dockerneoc/radon:pipeline-augment

ECHO "Complete!"
