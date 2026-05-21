/**
 * 平台管理 - 对象存储配置
 *
 * 配置 Listing Studio 图片上传与 8 图生成结果的存储后端（本地 / S3 兼容 R2·OSS）。
 */

import { useEffect, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { HardDrive, Loader2, PlugZap, Save } from 'lucide-react'
import { toast } from 'sonner'

import {
  adminStorageApi,
  type StorageConfigAdmin,
  type UpdateStorageConfigPayload,
} from '@/api/adminStorage'
import { apiV1Path } from '@/api/paths'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useUserStore } from '@/stores/user'

const QUERY_KEY = ['admin', 'storage']

function mbFromBytes(bytes: number): number {
  return Math.round(bytes / (1024 * 1024))
}

function bytesFromMb(mb: number): number {
  return mb * 1024 * 1024
}

function configToForm(config: StorageConfigAdmin): UpdateStorageConfigPayload {
  return {
    storage_type: config.storage_type,
    local_storage_path: config.local_storage_path,
    local_serve_prefix: config.local_serve_prefix,
    s3_bucket: config.s3_bucket,
    s3_region: config.s3_region,
    s3_endpoint_url: config.s3_endpoint_url,
    s3_access_key: config.s3_access_key,
    s3_public_base_url: config.s3_public_base_url,
    image_upload_max_bytes: config.image_upload_max_bytes,
    public_access: config.public_access,
    is_active: config.is_active,
  }
}

export default function AdminStoragePage(): React.JSX.Element {
  const { currentUser } = useUserStore()
  const isAdmin = currentUser?.role === 'admin'
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => adminStorageApi.get(),
    enabled: isAdmin,
  })

  const [form, setForm] = useState<UpdateStorageConfigPayload | null>(null)
  const [maxMb, setMaxMb] = useState(10)
  const [secretKey, setSecretKey] = useState('')

  useEffect(() => {
    if (data) {
      setForm(configToForm(data))
      setMaxMb(mbFromBytes(data.image_upload_max_bytes))
      setSecretKey('')
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: (payload: UpdateStorageConfigPayload) => adminStorageApi.update(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(QUERY_KEY, updated)
      setSecretKey('')
      toast.success('存储配置已保存')
    },
    onError: (err: Error) => toast.error(err.message || '保存失败'),
  })

  const testMutation = useMutation({
    mutationFn: () => adminStorageApi.testConnection(),
    onSuccess: (result) => toast.success(result.message),
    onError: (err: Error) => toast.error(err.message || '连接测试失败'),
  })

  if (!isAdmin) {
    return (
      <div className="container max-w-3xl py-8">
        <Alert variant="destructive">
          <AlertDescription>需要平台管理员权限</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (isLoading || !form) {
    return (
      <div className="container flex max-w-3xl items-center gap-2 py-8 text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        加载配置…
      </div>
    )
  }

  if (error) {
    return (
      <div className="container max-w-3xl py-8">
        <Alert variant="destructive">
          <AlertDescription>加载配置失败</AlertDescription>
        </Alert>
      </div>
    )
  }

  const isLocal = form.storage_type === 'local'
  const isS3 = form.storage_type === 's3'

  const handleSave = (): void => {
    const payload: UpdateStorageConfigPayload = {
      ...form,
      image_upload_max_bytes: bytesFromMb(maxMb),
      s3_secret_key: secretKey.trim() ? secretKey.trim() : undefined,
    }
    saveMutation.mutate(payload)
  }

  return (
    <div className="container max-w-3xl space-y-6 py-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold">
          <HardDrive className="h-6 w-6" />
          对象存储
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Listing Studio 用户上传与 8 图生成结果统一存储。支持本地目录或 S3 兼容（Cloudflare
          R2、阿里云 OSS）。
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>存储后端</CardTitle>
          <CardDescription>
            生产环境建议使用 R2/OSS 并配置公开读 URL；开发环境可使用 local。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>存储类型</Label>
            <Select
              value={form.storage_type}
              onValueChange={(v) => {
                setForm({ ...form, storage_type: v })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="local">本地 (local)</SelectItem>
                <SelectItem value="s3">S3 兼容 (s3)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isLocal && (
            <>
              <div className="space-y-2">
                <Label htmlFor="local_storage_path">本地目录</Label>
                <Input
                  id="local_storage_path"
                  value={form.local_storage_path ?? ''}
                  onChange={(e) => {
                    setForm({ ...form, local_storage_path: e.target.value })
                  }}
                  placeholder="./data/storage/images"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="local_serve_prefix">访问 URL 前缀</Label>
                <Input
                  id="local_serve_prefix"
                  value={form.local_serve_prefix ?? ''}
                  onChange={(e) => {
                    setForm({ ...form, local_serve_prefix: e.target.value })
                  }}
                  placeholder={apiV1Path('/listing-studio/images')}
                />
              </div>
            </>
          )}

          {isS3 && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="s3_bucket">Bucket</Label>
                  <Input
                    id="s3_bucket"
                    value={form.s3_bucket ?? ''}
                    onChange={(e) => {
                      setForm({ ...form, s3_bucket: e.target.value })
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="s3_region">Region</Label>
                  <Input
                    id="s3_region"
                    value={form.s3_region ?? ''}
                    onChange={(e) => {
                      setForm({ ...form, s3_region: e.target.value })
                    }}
                    placeholder="auto（R2）或 oss-cn-hangzhou"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="s3_endpoint_url">Endpoint URL</Label>
                <Input
                  id="s3_endpoint_url"
                  value={form.s3_endpoint_url ?? ''}
                  onChange={(e) => {
                    setForm({ ...form, s3_endpoint_url: e.target.value })
                  }}
                  placeholder="https://&lt;account&gt;.r2.cloudflarestorage.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="s3_public_base_url">公开读 URL 前缀</Label>
                <Input
                  id="s3_public_base_url"
                  value={form.s3_public_base_url ?? ''}
                  onChange={(e) => {
                    setForm({ ...form, s3_public_base_url: e.target.value })
                  }}
                  placeholder="https://cdn.example.com 或 R2.dev 子域"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="s3_access_key">Access Key</Label>
                  <Input
                    id="s3_access_key"
                    value={form.s3_access_key ?? ''}
                    onChange={(e) => {
                      setForm({ ...form, s3_access_key: e.target.value })
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="s3_secret_key">
                    Secret Key
                    {data?.secret_configured ? '（留空不修改）' : ''}
                  </Label>
                  <Input
                    id="s3_secret_key"
                    type="password"
                    value={secretKey}
                    onChange={(e) => {
                      setSecretKey(e.target.value)
                    }}
                    placeholder={data?.secret_configured ? '••••••••' : ''}
                  />
                </div>
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label htmlFor="max_mb">上传大小上限 (MB)</Label>
            <Input
              id="max_mb"
              type="number"
              min={1}
              max={100}
              value={maxMb}
              onChange={(e) => {
                setMaxMb(Number(e.target.value) || 10)
              }}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <Label>公开读</Label>
              <p className="text-xs text-muted-foreground">
                返回完整 HTTPS URL，前端可直接 img 引用
              </p>
            </div>
            <Switch
              checked={form.public_access ?? true}
              onCheckedChange={(v) => {
                setForm({ ...form, public_access: v })
              }}
            />
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <Button onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              保存
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                testMutation.mutate()
              }}
              disabled={testMutation.isPending}
            >
              {testMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <PlugZap className="mr-2 h-4 w-4" />
              )}
              测试连接
            </Button>
          </div>

          {data?.updated_at && (
            <p className="text-xs text-muted-foreground">上次更新：{data.updated_at}</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
