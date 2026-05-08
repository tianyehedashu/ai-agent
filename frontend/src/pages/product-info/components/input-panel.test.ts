/**
 * 产品信息输入区单测：inputsToUserInput
 */

import { describe, it, expect } from 'vitest'

import { inputsToUserInput } from './input-panel-shared'

describe('inputsToUserInput', () => {
  it('空输入返回空对象', () => {
    expect(inputsToUserInput({})).toEqual({})
  })

  it('部分字段会写入 user_input', () => {
    expect(
      inputsToUserInput({
        product_link: 'https://example.com/p',
        product_name: '商品A',
      })
    ).toEqual({
      product_link: 'https://example.com/p',
      product_name: '商品A',
    })
  })

  it('全部字段会写入 user_input', () => {
    expect(
      inputsToUserInput({
        product_link: 'https://a.com',
        competitor_link: 'https://b.com',
        product_name: 'Name',
        keywords: 'k1, k2',
        image_urls: ['https://img1.jpg', 'https://img2.jpg'],
      })
    ).toEqual({
      product_link: 'https://a.com',
      competitor_link: 'https://b.com',
      product_name: 'Name',
      keywords: 'k1, k2',
      image_urls: ['https://img1.jpg', 'https://img2.jpg'],
    })
  })

  it('空 image_urls 不写入', () => {
    expect(inputsToUserInput({ image_urls: [] })).toEqual({})
    expect(inputsToUserInput({ image_urls: undefined })).toEqual({})
  })
})
