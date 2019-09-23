/** @format */

import * as toast from './toast'

const fetch = window.fetch
// const {escape} = require('querystring')

function encodeFormData(data) {
  let urlEncodedDataPairs = []
  for (let name in data) {
    urlEncodedDataPairs.push(
      encodeURIComponent(name) + '=' + encodeURIComponent(data[name])
    )
  }
  return urlEncodedDataPairs.join('&').replace(/%20/g, '+')
}

function encodeNestedUrlParams(queryObj, nesting = '') {
  let queryString = ''

  const pairs = Object.entries(queryObj).map(([key, val]) => {
    // Handle the nested, recursive case, where the value to encode is an object itself
    if (typeof val === 'object') {
      return encodeNestedUrlParams(val, nesting + `${key}.`)
    } else {
      // Handle base case, where the value to encode is simply a string.
      return [nesting + key, val].map(encodeURIComponent).join('=')
    }
  })
  return pairs.join('&')
}

export default async function ajax({
  method = 'POST',
  json = true,
  endpoint,
  params,
  payload,
  onSuccess,
  onError,
  successMsg,
  errorMsg
}) {
  var r
  try {
    let body,
      url,
      headers = {}

    if (json) {
      headers['Accept'] = 'application/json'
      headers['Content-Type'] = 'application/json'
      body = payload && JSON.stringify(payload)
    } else {
      headers['Content-Type'] = 'application/x-www-form-urlencoded'
      body = encodeFormData(payload)
    }

    const querystr = params && encodeNestedUrlParams(params)
    url = querystr ? endpoint + '?' + querystr : endpoint

    let resp = await fetch(url, {
      method,
      credentials: 'same-origin',
      body,
      headers
    })
    r = json ? await resp.json() : await resp.text()
    if (!resp.ok || r.error) {
      errorMsg && toast.warning(r.error ? `${errorMsg}: ${r.error}` : errorMsg)
      onError && (await onError(r))
      return
    }
  } catch (e) {
    console.error(e)
    errorMsg &&
      toast.error(
        `${errorMsg}. <br>Unexpected error: if this error continues, please contact support.`,
        {timeout: 8000}
      )
    onError && (await onError(r))
    return
  }

  successMsg &&
    toast.success(typeof successMsg === 'function' ? successMsg(r) : successMsg)
  onSuccess && (await onSuccess(r))
}
