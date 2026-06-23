UPDATE gateway_models AS gm
SET real_model = 'openai/' || gm.real_model
FROM provider_credentials AS pc
WHERE gm.credential_id = pc.id
  AND gm.provider = 'openai'
  AND gm.real_model NOT LIKE '%/%'
  AND pc.api_base IS NOT NULL
  AND pc.api_base NOT ILIKE 'https://api.openai.com%';

UPDATE system_gateway_models AS sgm
SET real_model = 'openai/' || sgm.real_model
FROM system_provider_credentials AS spc
WHERE sgm.credential_id = spc.id
  AND sgm.provider = 'openai'
  AND sgm.real_model NOT LIKE '%/%'
  AND spc.api_base IS NOT NULL
  AND spc.api_base NOT ILIKE 'https://api.openai.com%';
