import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import RankingsView from './views/RankingsView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'rankings', component: RankingsView, meta: { title: 'Weekly Projections' } },
    { path: '/players/:id', name: 'player', component: () => import('./views/PlayerView.vue'), meta: { title: 'Player' } },
    { path: '/about', name: 'about', component: () => import('./views/AboutView.vue'), meta: { title: 'How It Works' } },
    { path: '/accuracy', name: 'accuracy', component: () => import('./views/AccuracyView.vue'), meta: { title: 'Scorecard' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const page = to.meta.title as string | undefined
  document.title = page ? `${page} · AI Fantasy Football Score Predictor` : 'AI Fantasy Football Score Predictor'
})

createApp(App).use(router).mount('#app')
