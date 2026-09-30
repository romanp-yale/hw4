import { Link } from 'react-router-dom'

export type ProductCardData = {
  product_id: string
  name: string
  garment_type: string
  description: string
  price: number
  image_url: string
}

export const money = (amount: number) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD',
}).format(amount)

export default function ProductCard({ product }: { product: ProductCardData }) {
  return <Link className="product-card" to={`/products/${encodeURIComponent(product.product_id)}`}>
    <div className="card-image"><img src={product.image_url} alt={product.name} loading="lazy" /><span className="card-arrow" aria-hidden="true">↗</span></div>
    <div className="card-content"><span className="eyebrow">{product.garment_type}</span><h3>{product.name}</h3><p>{product.description}</p><div className="card-bottom"><span className="price">{money(product.price)}</span><span className="card-view">View piece <span aria-hidden="true">↗</span></span></div></div>
  </Link>
}
