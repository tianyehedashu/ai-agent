/**
 * User API
 */

import { apiClient } from './client'

export interface CurrentUser {
  id: string
  email: string
  name: string
  is_anonymous: boolean
}

export interface LoginParams {
  email: string
  password: string
}

export interface RegisterParams {
  email: string
  password: string
  name?: string
}

interface LoginResponse {
  access_token: string
  token_type: string
}

export const userApi = {
  /**
   * 注册
   */
  async register(params: RegisterParams): Promise<CurrentUser> {
    // 1. 注册
    await apiClient.post<CurrentUser>('/api/v1/auth/register', {
      email: params.email,
      password: params.password,
      name: params.name,
      // 默认字段
      is_active: true,
      is_superuser: false,
      is_verified: false,
    })

    // 2. 自动登录
    return this.login({ email: params.email, password: params.password })
  },

  /**
   * 登录
   */
  async login(params: LoginParams): Promise<CurrentUser> {
    // 1. 获取 Token
    const response = await apiClient.postForm<LoginResponse>('/api/v1/auth/jwt/login', {
      username: params.email, // FastAPI Users 使用 username 字段接收 email
      password: params.password,
    })

    // 2. 保存 Token
    apiClient.setToken(response.access_token)

    // 3. 获取并返回用户信息
    return this.getCurrentUser()
  },

  /**
   * 获取当前用户信息
   */
  async getCurrentUser(): Promise<CurrentUser> {
    return await apiClient.get<CurrentUser>('/api/v1/auth/me')
  },

  /**
   * 退出登录
   * 清除所有认证信息（token、localStorage、cookie）
   */
  async logout(): Promise<void> {
    try {
      // 调用后端退出登录接口，清除 cookie
      await apiClient.post('/api/v1/auth/logout')
    } catch (error) {
      // 即使后端调用失败，也清除本地认证信息
      console.warn('Logout API call failed:', error)
    } finally {
      // 清除所有本地存储的认证信息（token 和 anonymousUserId）
      apiClient.clearAuth()
      
      // 尝试清除 anonymous_user_id cookie（作为备用方案）
      // 注意：如果 cookie 是 httpOnly，前端无法直接删除，主要依赖后端清除
      document.cookie = 'anonymous_user_id=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;'
    }
  },
}