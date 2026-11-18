package com.example.exercise;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/** These tests define a correct solution. They must pass unchanged. */
class GreetingTest {
    @Test
    void greetsByName() {
        assertEquals("Hello, Asha!", Greeting.of("Asha"));
    }

    @Test
    void ignoresSpaceAroundTheName() {
        assertEquals("Hello, Ben!", Greeting.of("  Ben "));
    }

    @Test
    void greetsTheWorldWhenThereIsNoName() {
        assertEquals("Hello, world!", Greeting.of(""));
        assertEquals("Hello, world!", Greeting.of("   "));
        assertEquals("Hello, world!", Greeting.of(null));
    }
}
