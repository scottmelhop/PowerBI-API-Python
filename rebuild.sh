pip uninstall pbiapi --y
poetry build
pip install ./dist/pbiapi-0.2.4-py3-none-any.whl
#cp ./dist/pbiapi-0.2.4-py3-none-any.whl ../../devops/powerbi_cicd_template/lib/pbiapi-0.2.4-py3-none-any.whl
#cd ../../devops/powerbi_cicd_template/
#git add lib/pbiapi-0.2.4-py3-none-any.whl
