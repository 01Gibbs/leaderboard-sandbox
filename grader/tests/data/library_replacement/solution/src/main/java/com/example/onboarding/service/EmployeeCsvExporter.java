package com.example.onboarding.service;

import com.opencsv.CSVWriter;
import com.example.onboarding.model.Employee;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.StringWriter;
import java.util.List;

/**
 * Writes employees as CSV (every field quoted, "\n" line endings), using opencsv 5.
 */
@Component
public class EmployeeCsvExporter {

    public String export(List<Employee> employees) {
        StringWriter out = new StringWriter();
        CSVWriter writer = new CSVWriter(out);
        try {
            writer.writeNext(new String[] {"id", "name", "role", "onboardingDate"});
            for (Employee e : employees) {
                writer.writeNext(new String[] {
                        String.valueOf(e.getId()), e.getName(), e.getRole(), String.valueOf(e.getOnboardingDate())
                });
            }
            writer.close();
        } catch (IOException ex) {
            throw new IllegalStateException("Could not write CSV", ex);
        }
        return out.toString();
    }
}
