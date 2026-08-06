FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci --legacy-peer-deps || npm install

COPY . .

# Environment variables for Next.js build
ARG NEXT_PUBLIC_API_BASE_URL=https://my-app-service-78389130178.asia-southeast1.run.app
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID=56976125302-vb1suvl9rm1esc9nib0lasuc764ume02.apps.googleusercontent.com
ARG NEXT_PUBLIC_SUPABASE_URL=https://wyzxcnbnosbhrkehuxuu.supabase.co
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_3raIcTDoeyYglaMVFwpFYg_sTnLCMwo

ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 8080

CMD ["node", "server.js"]
