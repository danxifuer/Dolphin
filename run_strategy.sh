S_NAME=$1
S_PATH=$2
if [ -n "$S_NAME" ] && [ -n "$S_PATH" ]; then
    nohup wingchun strategy -n $S_NAME -p $S_PATH &
else
    echo "Usage: run_strategy.sh strategy_name strategy_path"
fi