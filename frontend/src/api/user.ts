/**
 * User API
 */

import { apiV1Path } from '@/api/paths'
import { setRefreshToken } from '@/stores/auth'

import { apiClient } from './client'

export interface CurrentUser {
  id: string
  email: string
  name: string
  /** 用户角色：admin, user, viewer；仅管理员可管理动态工具 */
  role?: string
  /** 厂商系统操作用户 ID（如 GIIKIN creator_id） */
  vendor_creator_id?: number | null
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

export interface UpdateUserParams {
  name?: string
  avatar_url?: string
  vendor_creator_id?: number | null
}

interface TokenPairResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export const userApi = {
  /**
   * 注册
   */
  async register(params: RegisterParams): Promise<CurrentUser> {
    // 1. 注册
    await apiClient.post<CurrentUser>(apiV1Path('/auth/register'), {
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
   * 登录（使用增强 token 端点，返回 access + refresh token）
   */
  async login(params: LoginParams): Promise<CurrentUser> {
    // 1. 获取 Token Pair
    const response = await apiClient.post<TokenPairResponse>(apiV1Path('/auth/token'), {
      email: params.email,
      password: params.password,
    })

    // 2. 保存 Token Pair
    apiClient.setToken(response.access_token)
    setRefreshToken(response.refresh_token)

    // 3. 获取并返回用户信息
    return this.getCurrentUser()
  },

  /**
   * 获取当前用户信息
   */
  async getCurrentUser(): Promise<CurrentUser> {
    return await apiClient.get<CurrentUser>(apiV1Path('/auth/me'))
  },

  /**
   * 更新当前用户信息
   */
  async updateUser(params: UpdateUserParams): Promise<CurrentUser> {
    return await apiClient.put<CurrentUser>(apiV1Path('/auth/me'), params)
  },

  /**
   * 退出登录
   * 清除所有本地认证信息（token、localStorage）
   */
  async logout(): Promise<void> {
    try {
      // 调用后端退出登录接口
      await apiClient.post(apiV1Path('/auth/logout'))
    } catch (error) {
      // 即使后端调用失败，也清除本地认证信息
      console.warn('Logout API call failed:', error)
    } finally {
      apiClient.clearAuth()
    }
  },
}
