UPDATE gateway_models AS gm
SET real_model = substring(gm.real_model FROM 8)
FROM provider_credentials AS pc
WHERE gm.credential_id = pc.id
  AND gm.provider = 'openai'
  AND gm.real_model LIKE 'openai/%'
  AND pc.api_base IS NOT NULL
  AND pc.api_base NOT ILIKE 'https://api.openai.com%';

UPDATE system_gateway_models AS sgm
SET real_model = substring(sgm.real_model FROM 8)
FROM system_provider_credentials AS spc
WHERE sgm.credential_id = spc.id
  AND sgm.provider = 'openai'
  AND sgm.real_model LIKE 'openai/%'
  AND spc.api_base IS NOT NULL
  AND spc.api_base NOT ILIKE 'https://api.openai.com%';
