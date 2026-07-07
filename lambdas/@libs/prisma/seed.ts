import { PrismaClient } from "./generated/client";

const prisma = new PrismaClient();

const products = [
  {
    id: "0d8efc91-2f45-4e97-8239-7b87142b7b01",
    name: "Notebook",
    description: "Notebook para desenvolvimento",
    price: "3499.90",
  },
  {
    id: "8c791df3-2934-4b3e-9d2c-cf44e50e021a",
    name: "Mouse sem fio",
    description: "Mouse ergonomico com conexao bluetooth",
    price: "129.90",
  },
  {
    id: "ca4fb8a0-91ff-4ed7-926f-50365f95f6f0",
    name: "Teclado mecanico",
    description: "Teclado mecanico ABNT2 com switches tateis",
    price: "289.90",
  },
  {
    id: "f4981e3f-02a1-41ea-bb23-cf0f6a939b7e",
    name: "Monitor 27 polegadas",
    description: "Monitor IPS 27 polegadas com resolucao QHD",
    price: "1599.90",
  },
];

async function main(): Promise<void> {
  await prisma.product.createMany({
    data: products,
    skipDuplicates: true,
  });
}

main()
  .catch((error: unknown) => {
    console.error(error);
    throw error;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
