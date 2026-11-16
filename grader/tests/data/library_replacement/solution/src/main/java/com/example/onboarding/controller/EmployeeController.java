package com.example.onboarding.controller;

import com.example.onboarding.dto.OnboardingStatus;
import com.example.onboarding.model.Employee;
import com.example.onboarding.repository.EmployeeRepository;
import com.example.onboarding.service.EmployeeCsvExporter;
import com.example.onboarding.service.OnboardingStatusService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.util.List;

@RestController
@RequestMapping("/api/employees")
public class EmployeeController {

    private static final Logger log = LoggerFactory.getLogger(EmployeeController.class);

    private final EmployeeRepository repository;
    private final OnboardingStatusService statusService;
    private final EmployeeCsvExporter csvExporter;

    public EmployeeController(EmployeeRepository repository, OnboardingStatusService statusService,
                              EmployeeCsvExporter csvExporter) {
        this.repository = repository;
        this.statusService = statusService;
        this.csvExporter = csvExporter;
    }

    /** API 1: capture employee details. */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Employee create(@Valid @RequestBody Employee employee) {
        employee.setId(null); // always create a new record
        Employee saved = repository.save(employee);
        log.info("Employee created: id={}", saved.getId());
        return saved;
    }

    /** API 2: fetch all captured employee details. */
    @GetMapping
    public List<Employee> getAll() {
        return repository.findAll();
    }

    /**
     * API 3: how far away is this employee's onboarding date?
     * The optional asOf parameter (yyyy-MM-dd) replaces "today", which makes results repeatable.
     */
    @GetMapping("/{id}/onboarding-status")
    public OnboardingStatus onboardingStatus(@PathVariable Long id,
                                             @RequestParam(required = false)
                                             @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate asOf) {
        Employee employee = repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Employee not found"));
        return statusService.statusFor(employee, asOf != null ? asOf : LocalDate.now());
    }

    /** API 4: download all employees as CSV. */
    @GetMapping("/export")
    public ResponseEntity<String> export() {
        log.info("Employee export requested");
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("text/csv"))
                .header("Content-Disposition", "attachment; filename=\"employees.csv\"")
                .body(csvExporter.export(repository.findAll()));
    }
}
