> [!NOTE]  
> this wodle works on any Wazuh installation but this how-to assumes a multi-node [Wazuh docker deployment](https://github.com/wazuh/wazuh-docker) and may require adaptation for other deployment methods

# install wodle
Clone this repo in the directory where the Wazuh docker repo is cloned
```
> ls
wazuh-docker
> git clone https://github.com/avanwouwe/wazuh-atlassian.git
> ls
wazuh-docker/
wazuh-atlassian/
```

In the `docker-compose.yml` mount the `/wodle` directory of this repo so that it is available on the Wazuh master.
```
    volumes:
      - ../../wazuh-gworkspace/wodle:/var/ossec/wodles/atlassian
```

And then create a shell session on the master node:
```
docker ps
docker exec -ti <container id of master container> /bin/bash
cd /var/ossec/wodles/atlassian/
```

Create the configuration file by adapting and then running this command:
```
cat > config.json << EOF
{
 "orgId": "<your Org ID>",
 "apiKey": "<your API key>"
}
EOF
```

Your Org ID is the UUID in the URL when you use admin.atlassian.com. For example for the URL `https://admin.atlassian.com/o/e026e7a7-1112-463a-8534-71c4b6a8ee21/overview`
.. the Org ID is `e026e7a7-1112-463a-8534-71c4b6a8ee21`

See the [Atlassian documentation](https://confluence.atlassian.com/jirakb/what-it-is-the-organization-id-and-where-to-find-it-1207189876.html) for a more detailed description.

Atlassian propose an API that lists all the audit events available to your licence level, with some meta-data like the "action group". This meta data is stored in action.json. A default version is provided in this repo, and you can recover your version of the file by using the shell session on the master node we opened before and running :
```
./atlassian --actions
```

You can test that the wodle works by running it and checking that it outputs log events in JSON format. The --unread parameter ensures that the historical messages will be left unread for the next run. 
```
./gworkspace --unread
```

# add rules
Events only generate alerts if they are matched by a rule. Go to the rules configuration and create a new rules file `0772-atlassian_rules.xml` and fill it with the contents of [/rules/0772-atlassian_rules.xml](/rules/0772-atlassian_rules.xml).

# change ossec.conf
Add this wodle configuration to `/var/ossec/etc/ossec.conf` to ensure that the wodle is called periodically by Wazuh. In the Wazuh-provided Docker installion this file is modified in `~/wazuh-docker/multi-node/config/wazuh_cluster`.
```
  <wodle name="command">
    <disabled>no</disabled>
    <tag>atlassian</tag>
    <command>/var/ossec/wodles/atlassian/atlassian -o 24</command>
    <interval>5m</interval>
    <ignore_output>no</ignore_output>
    <run_on_start>yes</run_on_start>
    <timeout>0</timeout>
  </wodle>
```

This will run the wodle every 5 minutes. Running it more often will be more resource-intensive for Atlasian and running it is less often will mean that events arrive with more delay. More delay also means that the timestamps are incorrect, since Wazuh does not allow the JSON decoder to map a field to `@timestamp`, which is filled with the time of alert injection. The `data.timestamp`contains the real timestamp of the event.

The wodle keeps track of the most recent event that has been extracted for each service type, and will start extracting from that timepoint on at the next extraction. The `-o` parameter configures the offset, or the maximum number of hours to go back in time. If the offset goes back too far in history, the extraction will return a lot of data and may time out the first time you run it. And if the offset is too short it will result in missed events, should the wodle stop running for longth than that period.

Restart the server for the changes to take effect, for example using the `Restart cluster` button in the `Server Management` > `Status` menu.

You should start seeing new events show up in the Threat hunting module. You can filter for `data.atlassian.orgId: *` to make it easier to see.

![screenshot of Atlassian events in Wazuh](/doc/atlassian%20screenshot.png)
