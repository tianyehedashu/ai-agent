import { useState } from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { ChevronDown, Loader2, Lock, Mail, Terminal } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { initiateSsoLogin, isSsoMode, showLocalLogin } from '@/config/auth'
import { useToast } from '@/hooks/use-toast'
import { useUserStore, CURRENT_USER_QUERY_KEY } from '@/stores/user'

const formSchema = z.object({
  email: z.string().email({ message: '请输入有效的邮箱地址' }),
  password: z.string().min(1, { message: '请输入密码' }),
})

export default function LoginPage(): React.JSX.Element {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useUserStore()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [isLoading, setIsLoading] = useState(false)
  const [localFormExpanded, setLocalFormExpanded] = useState(false)
  const navState = location.state as { from?: string } | null | undefined
  const from = navState?.from ?? '/'

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  async function onSsoLogin(): Promise<void> {
    setIsLoading(true)
    try {
      await initiateSsoLogin(from)
    } catch (error) {
      toast({
        title: '无法跳转 SSO 登录',
        description: error instanceof Error ? error.message : 'SSO 登录初始化失败',
        variant: 'destructive',
      })
      setIsLoading(false)
    }
  }

  async function onSubmit(values: z.infer<typeof formSchema>): Promise<void> {
    setIsLoading(true)
    try {
      const user = await login(values)
      queryClient.setQueryData(CURRENT_USER_QUERY_KEY, user)
      await queryClient.invalidateQueries()
      toast({
        title: '登录成功',
        description: '欢迎回来！',
      })
      navigate(from, { replace: true })
    } catch (error) {
      toast({
        title: '登录失败',
        description: error instanceof Error ? error.message : '请检查用户名和密码',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const ssoSection = isSsoMode ? (
    <div className="space-y-4">
      <Button
        type="button"
        className="w-full bg-primary/90 shadow-lg shadow-primary/20 transition-all duration-300 hover:bg-primary"
        disabled={isLoading}
        onClick={() => {
          void onSsoLogin()
        }}
      >
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            跳转中...
          </>
        ) : (
          'Giikin SSO 登录'
        )}
      </Button>
      {showLocalLogin && (
        <>
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background/60 px-2 text-muted-foreground">或</span>
            </div>
          </div>
          <button
            type="button"
            className="flex w-full items-center justify-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            onClick={() => {
              setLocalFormExpanded((prev) => !prev)
            }}
          >
            邮箱密码登录
            <ChevronDown
              className={`h-4 w-4 transition-transform ${localFormExpanded ? 'rotate-180' : ''}`}
            />
          </button>
        </>
      )}
    </div>
  ) : null

  const localFormSection = (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>邮箱</FormLabel>
              <FormControl>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="name@example.com"
                    className="border-muted-foreground/20 bg-background/50 pl-9 transition-all duration-300 focus:border-primary/50 focus:ring-primary/20"
                    {...field}
                  />
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="password"
          render={({ field }) => (
            <FormItem>
              <FormLabel>密码</FormLabel>
              <FormControl>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    type="password"
                    placeholder="••••••••"
                    className="border-muted-foreground/20 bg-background/50 pl-9 transition-all duration-300 focus:border-primary/50 focus:ring-primary/20"
                    {...field}
                  />
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button
          type="submit"
          className="w-full bg-primary/90 shadow-lg shadow-primary/20 transition-all duration-300 hover:bg-primary"
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              登录中...
            </>
          ) : (
            '登录'
          )}
        </Button>
      </form>
    </Form>
  )

  return (
    <div className="auth-stage flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <Card className="relative z-10 w-full max-w-md border-border/70 bg-card/80 shadow-2xl shadow-black/10 backdrop-blur-xl dark:shadow-black/40">
        <CardHeader className="space-y-1 pb-6 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 ring-1 ring-primary/10">
            <Terminal className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">AI Agent</CardTitle>
          <CardDescription>
            {isSsoMode ? '使用 Giikin 企业账号登录' : '请输入您的凭证以继续访问'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* local 模式：直接展示邮箱表单 */}
          {!isSsoMode && localFormSection}

          {/* sso 模式：仅 SSO 按钮 */}
          {isSsoMode && !showLocalLogin && ssoSection}

          {/* hybrid 模式：SSO 按钮 + 折叠邮箱表单 */}
          {isSsoMode && showLocalLogin && (
            <>
              {ssoSection}
              <div
                className={`overflow-hidden transition-all duration-300 ${
                  localFormExpanded ? 'mt-4 max-h-96 opacity-100' : 'max-h-0 opacity-0'
                }`}
              >
                {localFormSection}
              </div>
            </>
          )}
        </CardContent>
        {showLocalLogin && !isSsoMode && (
          <CardFooter className="flex flex-col space-y-2 text-center text-sm text-muted-foreground">
            <p>
              还没有账号？{' '}
              <Button
                variant="link"
                className="px-0 font-semibold text-primary"
                onClick={() => {
                  navigate('/register')
                }}
              >
                立即注册
              </Button>
            </p>
            <p className="text-xs opacity-50">如果是开发环境，可以使用默认账号进行测试</p>
          </CardFooter>
        )}
      </Card>
    </div>
  )
}
