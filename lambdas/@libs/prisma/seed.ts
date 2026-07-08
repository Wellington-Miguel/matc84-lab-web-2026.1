import { PrismaClient } from "./generated/client";

const prisma = new PrismaClient();

const products = [
  {
    id: "0d8efc91-2f45-4e97-8239-7b87142b7b01",
    name: "Cerveja Pilsen 350ml",
    description: "Lata de cerveja pilsen clara e refrescante",
    price: "4.99",
    amount: 240,
  },
  {
    id: "8c791df3-2934-4b3e-9d2c-cf44e50e021a",
    name: "Cerveja IPA 500ml",
    description: "Garrafa de cerveja IPA com amargor intenso",
    price: "12.90",
    amount: 96,
  },
  {
    id: "ca4fb8a0-91ff-4ed7-926f-50365f95f6f0",
    name: "Refrigerante Cola 2L",
    description: "Garrafa de refrigerante sabor cola",
    price: "8.49",
    amount: 180,
  },
  {
    id: "f4981e3f-02a1-41ea-bb23-cf0f6a939b7e",
    name: "Refrigerante Guarana 2L",
    description: "Garrafa de refrigerante sabor guarana",
    price: "7.99",
    amount: 160,
  },
];

async function main(): Promise<void> {
  await prisma.$transaction(
    products.map((product) =>
      prisma.product.upsert({
        where: { id: product.id },
        create: product,
        update: {
          name: product.name,
          description: product.description,
          price: product.price,
          amount: product.amount,
          deletedAt: null,
        },
      }),
    ),
  );
}

main()
  .catch((error: unknown) => {
    console.error(error);
    throw error;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
