import { HttpTypes } from "@medusajs/types"
import ProductRail from "@modules/home/components/featured-products/product-rail"

export default async function FeaturedProducts({
  collection,
  region,
}: {
  collection: HttpTypes.StoreCollection
  region: HttpTypes.StoreRegion
}) {
  return (
    <li key={collection.id}>
      <ProductRail collection={collection} region={region} title="Featured Products" />
    </li>
  )
}
