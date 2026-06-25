import { RequestMethod } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import 'reflect-metadata';

import { AppModule } from './app.module.js';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  app.setGlobalPrefix('api', {
    exclude: [{ path: 'llms.txt', method: RequestMethod.GET }]
  });
  await app.listen(process.env.PORT ? Number(process.env.PORT) : 3001);
}

await bootstrap();
