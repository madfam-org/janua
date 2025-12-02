import { NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest) {
  // Get country from various headers
  const country =
    request.headers.get('x-vercel-ip-country') ||
    request.headers.get('cf-ipcountry') ||
    request.headers.get('x-country-code') ||
    'US'

  // Determine currency and payment provider based on country
  let currency = 'USD'
  let paymentProvider = 'fungies'

  if (country === 'MX') {
    currency = 'MXN'
    paymentProvider = 'conekta'
  } else if (['GB', 'UK'].includes(country)) {
    currency = 'GBP'
  } else if (['FR', 'DE', 'ES', 'IT', 'NL', 'BE', 'AT', 'PT', 'IE', 'FI'].includes(country)) {
    currency = 'EUR'
  } else if (country === 'CA') {
    currency = 'CAD'
  } else if (country === 'AU') {
    currency = 'AUD'
  } else if (country === 'JP') {
    currency = 'JPY'
  }

  return NextResponse.json({
    country,
    currency,
    paymentProvider,
    region: getRegion(country)
  })
}

function getRegion(country: string): string {
  const regions: Record<string, string[]> = {
    'North America': ['US', 'CA'],
    'Latin America': ['MX', 'BR', 'AR', 'CL', 'CO', 'PE'],
    'Europe': ['GB', 'UK', 'FR', 'DE', 'ES', 'IT', 'NL', 'BE', 'AT', 'PT', 'IE', 'FI', 'SE', 'NO', 'DK'],
    'Asia Pacific': ['JP', 'CN', 'KR', 'IN', 'AU', 'NZ', 'SG', 'HK', 'TW'],
    'Middle East': ['AE', 'SA', 'IL', 'EG'],
    'Africa': ['ZA', 'NG', 'KE', 'EG']
  }

  for (const [region, countries] of Object.entries(regions)) {
    if (countries.includes(country)) {
      return region
    }
  }

  return 'International'
}