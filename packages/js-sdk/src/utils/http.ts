import { PlintoError } from '../types';

export interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

export class HttpClient {
  private baseUrl: string;
  private headers: HeadersInit;
  private debug: boolean;

  constructor(baseUrl: string, headers: HeadersInit = {}, debug = false) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.headers = headers;
    this.debug = debug;
  }

  private buildUrl(path: string, params?: Record<string, string>): string {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, value);
      });
    }
    return url.toString();
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    const contentType = response.headers.get('content-type');
    const isJson = contentType?.includes('application/json');

    if (!response.ok) {
      let errorData: any = {};
      
      if (isJson) {
        try {
          errorData = await response.json();
        } catch {
          errorData = { message: response.statusText };
        }
      } else {
        errorData = { message: await response.text() || response.statusText };
      }

      const error = new Error(errorData.message || 'Request failed') as PlintoError;
      error.code = errorData.code || 'UNKNOWN_ERROR';
      error.statusCode = response.status;
      error.details = errorData.details;
      
      throw error;
    }

    if (response.status === 204) {
      return {} as T;
    }

    if (isJson) {
      return response.json();
    }

    return response.text() as unknown as T;
  }

  private log(method: string, url: string, options?: RequestInit): void {
    if (this.debug) {
      console.log(`[Plinto SDK] ${method} ${url}`, options);
    }
  }

  async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { params, ...fetchOptions } = options;
    const url = this.buildUrl(path, params);

    const requestOptions: RequestInit = {
      ...fetchOptions,
      method,
      headers: {
        'Content-Type': 'application/json',
        ...this.headers,
        ...fetchOptions.headers,
      },
    };

    if (fetchOptions.body && typeof fetchOptions.body === 'object') {
      requestOptions.body = JSON.stringify(fetchOptions.body);
    }

    this.log(method, url, requestOptions);

    try {
      const response = await fetch(url, requestOptions);
      return this.handleResponse<T>(response);
    } catch (error) {
      if (error instanceof Error) {
        const plintoError = error as PlintoError;
        if (!plintoError.code) {
          plintoError.code = 'NETWORK_ERROR';
        }
        throw plintoError;
      }
      throw error;
    }
  }

  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('GET', path, options);
  }

  async post<T>(path: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('POST', path, { ...options, body });
  }

  async put<T>(path: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PUT', path, { ...options, body });
  }

  async patch<T>(path: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>('PATCH', path, { ...options, body });
  }

  async delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>('DELETE', path, options);
  }

  setHeader(key: string, value: string): void {
    this.headers = { ...this.headers, [key]: value };
  }

  removeHeader(key: string): void {
    const headers = { ...this.headers } as Record<string, string>;
    delete headers[key];
    this.headers = headers;
  }
}