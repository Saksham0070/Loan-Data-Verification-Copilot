export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
export function createApi(token) {
  return async (path, options = {}) => {
    const response = await fetch(`${API_URL}/api${path}`, {...options,headers:{...(options.body instanceof FormData ? {} : { 'Content-Type':'application/json' }),...(token ? { Authorization:`Bearer ${token}` } : {})}})
    const payload = await (response.headers.get('content-type')?.includes('json') ? response.json() : response.text())
    if (!response.ok) throw new Error(typeof payload === 'string' ? payload : (payload.detail || 'Request failed'))
    return payload
  }
}
