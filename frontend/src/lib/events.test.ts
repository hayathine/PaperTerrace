import { describe, expect, it } from "vitest";
import { APP_EVENTS } from "./events";

describe("APP_EVENTS", () => {
	it("should have NOTES_UPDATED event name", () => {
		expect(APP_EVENTS.NOTES_UPDATED).toBe("notes-updated");
	});

	it("should have correct structure", () => {
		expect(APP_EVENTS).toHaveProperty("NOTES_UPDATED");
	});
});
