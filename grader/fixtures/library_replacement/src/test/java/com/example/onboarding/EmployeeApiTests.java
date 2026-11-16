package com.example.onboarding;

import com.example.onboarding.repository.EmployeeRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.matchesPattern;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * These tests describe the behaviour the application must keep while libraries are replaced.
 * They deliberately do not mention Joda-Time, log4j or opencsv.
 */
@SpringBootTest(properties = "DB_URL=jdbc:h2:mem:testdb")
@AutoConfigureMockMvc
@ExtendWith(OutputCaptureExtension.class)
class EmployeeApiTests {

    @Autowired
    MockMvc mvc;
    @Autowired
    EmployeeRepository repository;

    @BeforeEach
    void clean() {
        repository.deleteAll();
    }

    private String create(String name, String role, String date) throws Exception {
        String body = "{\"name\":\"" + name + "\",\"role\":\"" + role + "\",\"onboardingDate\":\"" + date + "\"}";
        String json = mvc.perform(post("/api/employees").contentType(MediaType.APPLICATION_JSON).content(body))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return json.replaceAll(".*\"id\":(\\d+).*", "$1");
    }

    @Test
    void createThenFetch() throws Exception {
        create("Asha Rao", "Engineer", "2026-11-10");
        mvc.perform(get("/api/employees"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].name").value("Asha Rao"))
                .andExpect(jsonPath("$[0].onboardingDate").value("2026-11-10"));
    }

    @Test
    void rejectsMissingFields() throws Exception {
        mvc.perform(post("/api/employees").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void upcomingStatusCountsDaysAndWorkingDays() throws Exception {
        // 2026-11-10 is a Tuesday. From Wednesday 4 Nov: Thu, Fri, (weekend), Mon, Tue = 4 working days.
        String id = create("Asha Rao", "Engineer", "2026-11-10");
        mvc.perform(get("/api/employees/" + id + "/onboarding-status").param("asOf", "2026-11-04"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value("Asha Rao"))
                .andExpect(jsonPath("$.onboardingDate").value("2026-11-10"))
                .andExpect(jsonPath("$.onboardingDateLabel").value("Tuesday, 10 November 2026"))
                .andExpect(jsonPath("$.daysUntilOnboarding").value(6))
                .andExpect(jsonPath("$.workingDaysUntilOnboarding").value(4))
                .andExpect(jsonPath("$.status").value("UPCOMING"));
    }

    @Test
    void startsTodayStatus() throws Exception {
        String id = create("Asha Rao", "Engineer", "2026-11-10");
        mvc.perform(get("/api/employees/" + id + "/onboarding-status").param("asOf", "2026-11-10"))
                .andExpect(jsonPath("$.daysUntilOnboarding").value(0))
                .andExpect(jsonPath("$.workingDaysUntilOnboarding").value(0))
                .andExpect(jsonPath("$.status").value("STARTS_TODAY"));
    }

    @Test
    void startedStatus() throws Exception {
        String id = create("Asha Rao", "Engineer", "2026-11-10");
        mvc.perform(get("/api/employees/" + id + "/onboarding-status").param("asOf", "2026-11-12"))
                .andExpect(jsonPath("$.daysUntilOnboarding").value(-2))
                .andExpect(jsonPath("$.workingDaysUntilOnboarding").value(0))
                .andExpect(jsonPath("$.status").value("STARTED"));
    }

    @Test
    void workingDaysSkipWeekends() throws Exception {
        // Onboarding Monday 16 Nov, from Friday 13 Nov: only Monday counts.
        String id = create("Ravi Kumar", "Analyst", "2026-11-16");
        mvc.perform(get("/api/employees/" + id + "/onboarding-status").param("asOf", "2026-11-13"))
                .andExpect(jsonPath("$.daysUntilOnboarding").value(3))
                .andExpect(jsonPath("$.workingDaysUntilOnboarding").value(1));
    }

    @Test
    void unknownEmployeeIsNotFound() throws Exception {
        mvc.perform(get("/api/employees/999999/onboarding-status"))
                .andExpect(status().isNotFound());
    }

    @Test
    void exportsCsvWithEveryFieldQuoted() throws Exception {
        create("Rao, Asha", "Engineer", "2026-11-10");
        String csv = mvc.perform(get("/api/employees/export"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("text/csv"))
                .andReturn().getResponse().getContentAsString();
        assertThat(csv).matches("(?s)\"id\",\"name\",\"role\",\"onboardingDate\"\n"
                + "\"\\d+\",\"Rao, Asha\",\"Engineer\",\"2026-11-10\"\n");
    }

    @Test
    void exportOfEmptyListIsJustTheHeader() throws Exception {
        mvc.perform(get("/api/employees/export"))
                .andExpect(content().string("\"id\",\"name\",\"role\",\"onboardingDate\"\n"));
    }

    @Test
    void creatingAnEmployeeIsLogged(CapturedOutput output) throws Exception {
        String id = create("Asha Rao", "Engineer", "2026-11-10");
        assertThat(output.getAll()).contains("Employee created: id=" + id);
    }
}
