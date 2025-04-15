#!/bin/bash


# edit  docker/grafana/provisioning/dashboards/Main\ Dashboard.json
#
ENV=".env"

ask_yes_no() {
    while true; do
        read -p "" yn
        case $yn in
            [Yy]* ) return 0;; # Return 0 for Yes
            [Nn]* ) return 1;; # Return 1 for No
            * ) echo "Please answer yes or no.";;
        esac
    done
}

if [ ! -e ${ENV} ];then
	echo "Requires a valid ${ENV} to continue. Terminating setup."
	exit 1
fi

source .env

echo "Editing grafana dashboard Main Dashboard template"
echo "Using ${GRAFANA_HOST:-localhost} for grafana hostname"
echo "Using ${GRAFANA_PORT:-3000} for grafana port"


/bin/echo -n "add lat/long for your region into the Main grafana dashboard? [Y|N]"
if ask_yes_no
then
	/bin/echo -n "latitude "
	read LOCAL_LAT
	/bin/echo -n "longitude "
	read LOCAL_LONG
fi

/usr/bin/sed	-e "s/GRAFANA_HOST/${GRAFANA_HOST:-localhost}/g" \
					-e "s/GRAFANA_PORT/${GRAFANA_PORT:-3003}/g" \
					-e "s/LOCAL_LAT/${LOCAL_LAT:-32.008273}/g" \
					-e "s/LOCAL_LONG/${LOCAL_LONG:-34.969099}/g" \
					docker/grafana/provisioning/dashboards/Main\ Dashboard.json.tmpl > docker/grafana/provisioning/dashboards/Main\ Dashboard.json || (echo "failed to update template, exiting"; exit 1)

echo "done! proceeding to standing up the docker containers"
#docker compose up -d || (echo "failed to stand up docker containers, exiting"; exit 1)

exit 0
