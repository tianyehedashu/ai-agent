import { useState } from 'react'

import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2, Lock, Mail, Terminal, User } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
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
import { useToast } from '@/hooks/use-toast'
import { useUserStore } from '@/stores/user'

const formSchema = z
  .object({
    name: z.string().min(2, { message: '用户名至少需要2个字符' }),
    email: z.string().email({ message: '请输入有效的邮箱地址' }),
    password: z.string().min(8, { message: '密码长度至少为8位' }),
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: '两次输入的密码不一致',
    path: ['confirmPassword'],
  })

export default function RegisterPage(): React.JSX.Element {
  const navigate = useNavigate()
  const { register } = useUserStore()
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(false)

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  })

  async function onSubmit(values: z.infer<typeof formSchema>): Promise<void> {
    setIsLoading(true)
    try {
      await register({
        name: values.name,
        email: values.email,
        password: values.password,
      })
      toast({
        title: '注册成功',
        description: '账号已创建并自动登录',
      })
      navigate('/')
    } catch (error) {
      toast({
        title: '注册失败',
        description: error instanceof Error ? error.message : '请稍后重试',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background">
      {/* Dynamic Background Effects */}
      <div className="absolute inset-0 z-0">
        <div className="absolute -right-1/4 -top-1/4 h-1/2 w-1/2 rounded-full bg-purple-500/10 blur-[120px]" />
        <div className="absolute -bottom-1/4 -left-1/4 h-1/2 w-1/2 rounded-full bg-blue-500/10 blur-[120px]" />
      </div>

      <Card className="relative z-10 w-full max-w-md border-border/50 bg-background/60 shadow-xl backdrop-blur-xl">
        <CardHeader className="space-y-1 pb-6 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 ring-1 ring-primary/20">
            <Terminal className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">创建账号</CardTitle>
          <CardDescription>填写以下信息以开始使用 AI Agent</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>用户名</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <User className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          placeholder="您的称呼"
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
                          placeholder="至少8位字符"
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
                name="confirmPassword"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>确认密码</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                          type="password"
                          placeholder="再次输入密码"
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
                    注册中...
                  </>
                ) : (
                  '注册'
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
        <CardFooter className="flex justify-center text-sm text-muted-foreground">
          <p>
            已有账号？{' '}
            <Button
              variant="link"
              className="px-0 font-semibold text-primary"
              onClick={() => {
                navigate('/login')
              }}
            >
              直接登录
            </Button>
          </p>
        </CardFooter>
      </Card>
    </div>
  )
}
