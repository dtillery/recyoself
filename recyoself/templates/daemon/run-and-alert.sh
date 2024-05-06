echo "$(date +'%Y-%m-%dT%H:%M:%S') Recyoselfx run-and-notify: ${RECYOSELF_DAEMON_CMD_ARGS}"
cmd="$RECYOSELF_DAEMON_CMD $RECYOSELF_DAEMON_CMD_ARGS"
foundItineraries=$($cmd)
if [ -n "$foundItineraries" ]; then
    echo "Results returned, sending alert..."
    himalaya template write \
        --header Subject:"Recyoself Alert: ${RECYOSELF_DAEMON_NOTIFY_NAME}" \
        --header From:$RECYOSELF_DAEMON_EMAIL \
        --header To:$RECYOSELF_DAEMON_EMAIL \
        "$foundItineraries" \
    | himalaya template send
else
    echo "No results returned, not sending alert."
fi
