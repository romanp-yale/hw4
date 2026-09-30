import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { AccountPage, LoginPage, RegisterPage, useAuth } from './Auth'
import Chat from './Chat'
import ProductCard, { money, type ProductCardData } from './ProductCard'
import './chat-results.css'
import './usability.css'

type Inventory = { size: string; quantity: number }
type Product = ProductCardData & {
  colors: string[]
  search_tags: string[]
  total_stock?: number
  available_sizes?: string[]
  inventory?: Inventory[]
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

function Header() {
  const { user } = useAuth()
  const links = [
    ['/', 'Home'], ['/products', 'Products'], ['/about', 'About Us'],
    ...(user ? [['/account', 'My account']] : [['/login', 'Log in'], ['/create-account', 'Create account']]),
  ]
  return <>
    <div className="announcement">A little New Haven spirit, wherever you go <span>✦</span> Campus Customs</div>
    <header className="site-header">
      <Link to="/" className="brand" aria-label="Campus Customs home"><span className="brand-mark">Y</span><span>CAMPUS<br /><strong>CUSTOMS</strong></span></Link>
      <nav aria-label="Main navigation">{links.map(([to, label]) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => isActive ? 'active' : ''}>{label}</NavLink>)}</nav>
    </header>
  </>
}

function useProducts() {
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    getJson<Product[]>('/api/products').then(setProducts).catch((e: Error) => setError(e.message)).finally(() => setLoading(false))
  }, [])
  return { products, error, loading }
}

function Home() {
  const { products, error, loading } = useProducts()
  const featured = products.filter(p => ['basic-hoodie-big-yale', 'big-yale-tri-blend-t-shirt', 'champion-reverse-weave-crewneck', 'school-of-management-crest-t-shirt'].includes(p.product_id))
  const heroProduct = products.find(p => p.product_id === 'basic-hoodie-big-yale')
  return <main>
    <section className="hero"><div className="hero-inner"><span className="eyebrow">CAMPUS CUSTOMS  /  NEW HAVEN, CT</span><h1>Wear your Yale<br /><em>story.</em></h1><p>For game days, late nights, and every moment that feels like campus. Find layers and everyday favorites made for your corner of Yale.</p><Link className="button primary" to="/products">Explore the collection <span>↗</span></Link><div className="hero-footnote"><span>NEW HAVEN / CT</span><span>THE CAMPUS EDIT · FALL 2026</span></div></div><div className="hero-art"><div className="hero-orbit" aria-hidden="true">CAMPUS CUSTOMS / NEW HAVEN / CAMPUS CUSTOMS / NEW HAVEN /</div>{heroProduct ? <Link className="hero-product" to={`/products/${heroProduct.product_id}`} aria-label={`View ${heroProduct.name}`}><img src={heroProduct.image_url} alt={heroProduct.name} /><span className="hero-product-label"><small>THE EVERYDAY LAYER</small><strong>{heroProduct.name}</strong><span>Discover this piece ↗</span></span></Link> : <div className="hero-ring" aria-hidden="true">Y</div>}<span className="hero-art-caption">MADE FOR BULLDOG DAYS</span></div></section>
    <section className="section intro"><div><span className="eyebrow">THE CAMPUS EDIT</span><h2>From the classroom<br />to the stands.</h2></div><p>Represent your team, residential college, school, or the place you call home. Our shop brings Yale-inspired styles together so finding your next favorite is simple.</p></section>
    <section className="section featured"><div className="section-heading"><div><span className="eyebrow">HANDPICKED FROM THE CATALOGUE</span><h2>Start here</h2></div><Link to="/products" className="text-link">Shop all products ↗</Link></div>{loading ? <p className="status">Loading products…</p> : error ? <p className="status error" role="alert">Products are unavailable: {error}</p> : <div className="product-grid">{featured.map(p => <ProductCard key={p.product_id} product={p} />)}</div>}</section>
    <section className="closing"><span className="eyebrow">YOUR CAMPUS. YOUR COLORS.</span><h2>A good day to wear blue.</h2><Link to="/products" className="button light">Browse the shop ↗</Link></section>
  </main>
}

function Products() {
  const { products, error, loading } = useProducts()
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All styles')
  const [sort, setSort] = useState('name')
  const [size, setSize] = useState('Any size')
  const categories = ['All styles', ...new Set(products.map(p => p.garment_type))]
  const visible = products.filter(p => (category === 'All styles' || p.garment_type === category) && (size === 'Any size' || p.available_sizes?.includes(size)) && `${p.name} ${p.description} ${p.search_tags.join(' ')}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'price-low' ? a.price - b.price || a.name.localeCompare(b.name) : sort === 'price-high' ? b.price - a.price || a.name.localeCompare(b.name) : a.name.localeCompare(b.name))
  return <main className="page"><div className="page-title"><span className="eyebrow">CAMPUS CUSTOMS / THE COLLECTION</span><h1>Find your<br /><em>new favorite.</em></h1><p>Explore the catalogue. Prices and product details below come from the local Campus Customs database.</p></div>
    <div className="catalogue-controls"><label className="search-label">Search the collection<input value={query} onChange={e => setQuery(e.target.value)} placeholder="Try hoodie, baseball, college…" /></label><label className="filter-label">Style<select value={category} onChange={e => setCategory(e.target.value)}>{categories.map(c => <option key={c}>{c}</option>)}</select></label><label className="filter-label">Sort by<select value={sort} onChange={e => setSort(e.target.value)}><option value="name">Name A–Z</option><option value="price-low">Price: low to high</option><option value="price-high">Price: high to low</option></select></label><label className="filter-label">Available in size<select value={size} onChange={e => setSize(e.target.value)}>{['Any size', 'XS', 'S', 'M', 'L', 'XL', 'XXL'].map(option => <option key={option}>{option}</option>)}</select></label></div>
    {loading ? <p className="status">Loading products…</p> : error ? <p className="status error" role="alert">Could not load the catalogue: {error}. Check that the backend and local data pack are available.</p> : <><div className="result-count">{visible.length} {visible.length === 1 ? 'product' : 'products'}</div>{visible.length ? <div className="product-grid">{visible.map(p => <ProductCard key={p.product_id} product={p} />)}</div> : <p className="status">No products match those filters.</p>}</>}
  </main>
}

function RelatedProducts({ product }: { product: Product }) {
  const { products, error, loading } = useProducts()
  const related = products.filter(item => item.product_id !== product.product_id && item.garment_type === product.garment_type).slice(0, 4)
  return <section className="related-products" aria-label="Related products"><div className="section-heading"><div><span className="eyebrow">KEEP EXPLORING</span><h2>More {product.garment_type.toLowerCase()} styles</h2></div><Link to="/products" className="text-link">All products ↗</Link></div>{loading ? <p className="status">Loading related products…</p> : error ? <p className="status error" role="alert">Related products are unavailable: {error}</p> : related.length ? <div className="product-grid">{related.map(item => <ProductCard key={item.product_id} product={item} />)}</div> : <p className="status">No other styles in this category are listed.</p>}</section>
}

function ProductDetail() {
  const { productId } = useParams()
  const [product, setProduct] = useState<Product | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!productId) return
    setProduct(null)
    setError('')
    getJson<Product>(`/api/products/${encodeURIComponent(productId)}`).then(setProduct).catch((e: Error) => setError(e.message))
  }, [productId])
  return <main className="page detail-page"><Link to="/products" className="back-link">← Back to products</Link>{error ? <p className="status error" role="alert">{error}</p> : !product ? <p className="status">Loading product…</p> : <div className="detail-layout"><div className="detail-image"><img src={product.image_url} alt={product.name} /></div><div className="detail-info"><span className="eyebrow">{product.garment_type}</span><h1>{product.name}</h1><p className="detail-price">{money(product.price)}</p><div className="divider" /><h2>About this piece</h2><p className="description">{product.description}</p><h2>Colors</h2><div className="chips">{product.colors.map(color => <span key={color}>{color}</span>)}</div><h2>Sizes & stock</h2>{product.inventory?.length ? <div className="size-grid">{product.inventory.map(({ size, quantity }) => <div className={quantity > 0 ? 'size-chip' : 'size-chip unavailable'} key={size}><strong>{size}</strong><small>{quantity > 0 ? `${quantity} available` : 'Out of stock'}</small></div>)}</div> : <p className="muted">Size availability is not listed for this product.</p>}<p className="stock-note">Stock is shown from the local database and may change. Checkout is not available in this first version.</p></div></div>}{product && <RelatedProducts product={product} />}</main>
}

function About() {
  return <main className="page about-page"><div className="about-hero"><span className="eyebrow">ABOUT CAMPUS CUSTOMS</span><h1>Made for the<br /><em>Yale in you.</em></h1><p>Every Bulldog has a different route through New Haven. We bring the tees, layers, and small reminders that help you carry yours along.</p></div><div className="about-grid"><article><span className="number">01 /</span><h2>Campus roots</h2><p>From first semester to reunion weekend, what you wear can hold a memory. Our collection celebrates the places, people, and traditions that make campus personal.</p></article><article><span className="number">02 /</span><h2>Find your fit</h2><p>Browse by team, school, or everyday style. Product pages show details, colors, prices, and the sizes currently recorded in our local catalogue.</p></article><article><span className="number">03 /</span><h2>Here to help</h2><p>Need a place to start? Ask our shop assistant about styles, colors, prices, and size availability from the current catalogue.</p></article></div><Link className="button primary" to="/products">Explore products ↗</Link></main>
}

function Footer() { return <footer><Link to="/" className="footer-brand">CAMPUS CUSTOMS</Link><p>New Haven spirit, ready for wherever you go.</p><span>New Haven, Connecticut · Made for Bulldog days</span></footer> }

export default function App() {
  const location = useLocation()
  const [matches, setMatches] = useState<{ query: string; products: ProductCardData[] } | null>(null)
  useEffect(() => { setMatches(null) }, [location.pathname])
  useEffect(() => {
    if (matches?.products.length) document.getElementById('chat-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [matches])
  return <><Header />{matches?.products.length ? <section id="chat-results" className="section chat-results" aria-label="Chat product matches"><div className="section-heading"><div><span className="eyebrow">FOUND IN THE CATALOGUE</span><h2>Matches for “{matches.query}”</h2><p>{matches.products.length} {matches.products.length === 1 ? 'product' : 'products'} from your chat</p></div><button className="chat-results-close" onClick={() => setMatches(null)} aria-label="Dismiss chat results">×</button></div><div className="product-grid">{matches.products.map(product => <ProductCard key={product.product_id} product={product} />)}</div></section> : null}<Routes><Route path="/" element={<Home />} /><Route path="/products" element={<Products />} /><Route path="/products/:productId" element={<ProductDetail />} /><Route path="/about" element={<About />} /><Route path="/login" element={<LoginPage />} /><Route path="/create-account" element={<RegisterPage />} /><Route path="/account" element={<AccountPage />} /><Route path="*" element={<main className="page account-page"><h1>Page not found</h1><Link to="/">Return home</Link></main>} /></Routes><Footer /><Chat onResults={(query, products) => setMatches(products.length ? { query, products } : null)} /></>
}
