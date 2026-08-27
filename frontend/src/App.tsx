import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety'
import SpaIcon from '@mui/icons-material/Spa'
import { AppBar, Badge, Box, Button, Container, Stack, Toolbar, Typography } from '@mui/material'
import { Link as RouterLink, Route, Routes } from 'react-router-dom'
import { ChatWidget } from './components/ChatWidget'
import { CurrencySwitcher } from './components/CurrencySwitcher'
import { Allergies } from './pages/Allergies'
import { Home } from './pages/Home'
import { Product } from './pages/Product'
import { Quiz } from './pages/Quiz'
import { Results } from './pages/Results'
import { Search } from './pages/Search'
import { useSkinProfile } from './hooks/useSkinProfile'

function Header() {
  const { profile } = useSkinProfile()
  const avoiding = profile?.avoid_ingredients.length ?? 0

  return (
    <AppBar position="sticky">
      <Container maxWidth="lg">
        <Toolbar disableGutters sx={{ gap: 1 }}>
          <Stack
            component={RouterLink}
            to="/"
            direction="row"
            spacing={1}
            alignItems="center"
            sx={{ textDecoration: 'none', color: 'inherit', flexGrow: 1 }}
          >
            <SpaIcon sx={{ color: 'primary.main' }} />
            <Typography variant="h4" component="span" sx={{ letterSpacing: '-0.02em' }}>
              Dewdrop
            </Typography>
          </Stack>

          <CurrencySwitcher />

          <Button component={RouterLink} to="/search" color="inherit">
            Browse
          </Button>
          <Button
            component={RouterLink}
            to="/allergies"
            color="inherit"
            startIcon={
              <Badge badgeContent={avoiding} color="error">
                <HealthAndSafetyIcon fontSize="small" />
              </Badge>
            }
          >
            Allergies
          </Button>
          <Button component={RouterLink} to="/quiz" variant="contained" size="small">
            Skin quiz
          </Button>
        </Toolbar>
      </Container>
    </AppBar>
  )
}

function Footer() {
  return (
    <Box component="footer" sx={{ borderTop: 1, borderColor: 'divider', mt: 8, py: 4 }}>
      <Container maxWidth="lg">
        <Typography variant="caption" color="text.secondary">
          Dewdrop compares skincare prices and analyses ingredient lists. Ingredient
          information is educational and is not medical advice — for a persistent skin
          condition, see a dermatologist. Allergen screening compares your list against
          published ingredient lists only; it cannot account for reformulation,
          cross-contamination or “may contain” traces.
        </Typography>
      </Container>
    </Box>
  )
}

export default function App() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Header />
      <Box sx={{ flexGrow: 1 }}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Search />} />
          <Route path="/product/:slug" element={<Product />} />
          <Route path="/quiz" element={<Quiz />} />
          <Route path="/allergies" element={<Allergies />} />
          <Route path="/results" element={<Results />} />
        </Routes>
      </Box>
      <Footer />
      <ChatWidget />
    </Box>
  )
}
