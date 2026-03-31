#!/bin/bash
##USFUL DEBUG##
#printf "$CRM_alert_node $CRM_alert_rsc $CRM_alert_task $CRM_alert_kind $CRM_alert_desc $CRM_alert_attribute_name $CRM_alert_attribute_value" | ncat -u 255.255.255.255 5595
#echo "`date` $CRM_alert_node $CRM_alert_rsc $CRM_alert_task $CRM_alert_kind $CRM_alert_desc $CRM_alert_attribute_name $CRM_alert_attribute_value" >> /tmp/pacemaker
#printf "FairCom FailOver Event" | ncat -u 255.255.255.255 5595
##END OF USEFUL DEBUG##
if [[ $CRM_alert_rsc == "VIP" && $CRM_alert_task == "start" && $CRM_alert_desc == "ok" ]]; then
  printf "FairCom FailOver Event" | ncat -u 255.255.255.255 5595
#  echo "`date` Brodcast Sent" >> /tmp/pacemaker
fi

