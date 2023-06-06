lst=$(echo hello world peter)
PYTHON_EXECS=($lst)
# IFS=':' read -a PYTHON_EXECS <
for PYTHON_EXEC in "${PYTHON_EXECS[@]}"
do
    echo "Found $PYTHON_EXEC"
done