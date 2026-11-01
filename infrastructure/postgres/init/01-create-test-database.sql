-- Banco exclusivo da suíte de testes: os testes limpam tabelas, então nunca
-- devem tocar `quant_platform` (dev). Roda só na criação do volume; para um
-- volume já existente, ver infrastructure/README.md.
CREATE DATABASE quant_platform_test;
