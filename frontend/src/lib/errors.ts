/**
 * ユーザーに表示するメッセージの i18n キー定数。
 * 実際の文言は frontend/src/locales/ja.json・en.json で管理する。
 *
 * 使用例:
 *   const { t } = useTranslation();
 *   t(ERROR_KEYS.common.network)
 */
export const ERROR_KEYS = {
	common: {
		unexpected: "common.errors.unexpected",
		loadFailed: "common.errors.load_failed",
		uploadFailed: "common.errors.upload_failed",
		fileTooLarge: "common.errors.file_too_large",
		fileTypeInvalid: "common.errors.file_type_invalid",
		imageTooLarge: "common.errors.image_too_large",
		processing: "common.errors.processing",
		network: "common.errors.network",
	},
	errorBoundary: {
		title: "common.error_boundary.title",
		description: "common.error_boundary.description",
		reload: "common.error_boundary.reload",
	},
	figure: {
		analysisFailed: "viewer.figure_analysis_failed",
		analysisNetworkError: "viewer.figure_analysis_network_error",
	},
	dictionary: {
		unavailable: "viewer.dictionary.error_unavailable",
		translationUnavailable: "viewer.dictionary.error_translation_unavailable",
		truncatedNotice: "viewer.dictionary.truncated_notice",
	},
	auth: {
		loginFailed: "auth.login_failed",
	},
	chat: {
		errorRetry: "chat.error_retry",
	},
	contact: {
		error: "contact.error",
	},
	outage: {
		maintenanceTitle: "outage.maintenance_title",
		outageTitle: "outage.outage_title",
		maintenanceMessage: "outage.maintenance_message",
		outageMessage: "outage.outage_message",
	},
} as const;
