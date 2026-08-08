import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

function readStoredTheme(): Theme | null {
    try {
        const stored = localStorage.getItem(STORAGE_KEY)
        return stored === 'light' || stored === 'dark' ? stored : null
    } catch {
        return null
    }
}

function readSystemTheme(): Theme {
    return window.matchMedia(DARK_QUERY).matches ? 'dark' : 'light'
}

export function useTheme() {
    const [theme, setThemeState] = useState<Theme>(() => readStoredTheme() ?? readSystemTheme())

    useEffect(() => {
        document.documentElement.dataset.theme = theme
    }, [theme])

    useEffect(() => {
        if (readStoredTheme() !== null) return

        const query = window.matchMedia(DARK_QUERY)
        const onChange = (event: MediaQueryListEvent) => setThemeState(event.matches ? 'dark' : 'light')
        query.addEventListener('change', onChange)
        return () => query.removeEventListener('change', onChange)
    }, [theme])

    const setTheme = useCallback((next: Theme) => {
        try {
            localStorage.setItem(STORAGE_KEY, next)
        } catch {
        }
        setThemeState(next)
    }, [])

    const toggleTheme = useCallback(() => {
        setTheme(theme === 'dark' ? 'light' : 'dark')
    }, [theme, setTheme])

    return { theme, setTheme, toggleTheme }
}
