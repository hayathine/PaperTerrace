// Performance optimization configuration
// Centralized settings for all performance-related features

export const PERFORMANCE_CONFIG = {
	// Virtual scrolling settings
	virtualScroll: {
		overscanCount: 2,
		estimatedPageHeight: 800,
	},

	// Intersection observer for lazy rendering
	intersectionObserver: {
		rootMargin: "200px",
		threshold: 0.01,
	},

	// Animation settings
	animations: {
		disableInfiniteAnimations: true,
	},
} as const;

// Feature flags for gradual rollout of performance optimizations
export const PERF_FLAGS = {
	cssOptimizations: true,
	wordOverlayLazyRender: true,
	eventDelegation: true,
	reducedAnimations: true,
	performanceMonitoring: import.meta.env.DEV,
} as const;
