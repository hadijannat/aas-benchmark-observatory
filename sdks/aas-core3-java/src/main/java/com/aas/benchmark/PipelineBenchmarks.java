package com.aas.benchmark;

import aas_core.aas3_0.jsonization.Jsonization;
import aas_core.aas3_0.types.enums.DataTypeDefXsd;
import aas_core.aas3_0.types.impl.Property;
import aas_core.aas3_0.types.interfaces.IClass;
import aas_core.aas3_0.types.interfaces.IEnvironment;
import aas_core.aas3_0.types.interfaces.IProperty;
import aas_core.aas3_0.verification.Reporting;
import aas_core.aas3_0.verification.Verification;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.openjdk.jmh.annotations.*;
import org.openjdk.jmh.results.format.ResultFormatType;
import org.openjdk.jmh.runner.Runner;
import org.openjdk.jmh.runner.RunnerException;
import org.openjdk.jmh.runner.options.Options;
import org.openjdk.jmh.runner.options.OptionsBuilder;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(1)
@State(Scope.Benchmark)
public class PipelineBenchmarks {

    @Param({})
    public String dataset;

    private String rawJson;
    private JsonNode jsonNode;
    private IEnvironment env;
    private final ObjectMapper mapper = new ObjectMapper();

    @Setup(Level.Trial)
    public void setup() throws IOException {
        String datasetsDir = System.getenv("DATASETS_DIR");
        if (datasetsDir == null || datasetsDir.isEmpty()) {
            throw new IllegalStateException("DATASETS_DIR environment variable not set");
        }

        Path filePath = Path.of(datasetsDir, dataset + ".json");
        rawJson = Files.readString(filePath);
        jsonNode = mapper.readTree(rawJson);
        env = Jsonization.Deserialize.deserializeEnvironment(jsonNode);
    }

    @Benchmark
    public IEnvironment deserialize() throws Exception {
        JsonNode node = mapper.readTree(rawJson);
        return Jsonization.Deserialize.deserializeEnvironment(node);
    }

    @Benchmark
    public int validate() {
        int errorCount = 0;
        for (Reporting.Error error : Verification.verify(env)) {
            errorCount++;
        }
        return errorCount;
    }

    @Benchmark
    public int traverse() {
        int count = 0;
        for (IClass node : env.descend()) {
            count++;
        }
        return count;
    }

    @Benchmark
    public int update() {
        int count = 0;
        for (IClass node : env.descend()) {
            if (node instanceof IProperty prop) {
                if (prop.getValue().isPresent()) {
                    prop.setValue(prop.getValue().get() + "_updated");
                    count++;
                }
            }
        }
        return count;
    }

    @Benchmark
    public JsonNode serialize() {
        return Jsonization.Serialize.toJsonObject(env);
    }

    public static void main(String[] args) throws RunnerException, IOException {
        // Discover datasets dynamically
        String datasetsDir = System.getenv("DATASETS_DIR");
        if (datasetsDir == null || datasetsDir.isEmpty()) {
            throw new IllegalStateException("DATASETS_DIR environment variable not set");
        }

        File dir = new File(datasetsDir);
        File[] jsonFiles = dir.listFiles((d, name) -> name.endsWith(".json"));
        if (jsonFiles == null || jsonFiles.length == 0) {
            throw new IllegalStateException("No JSON files found in " + datasetsDir);
        }

        String[] datasetNames = new String[jsonFiles.length];
        for (int i = 0; i < jsonFiles.length; i++) {
            String name = jsonFiles[i].getName();
            datasetNames[i] = name.substring(0, name.length() - 5);
        }

        String outputPath = System.getenv("JMH_OUTPUT");
        if (outputPath == null) {
            outputPath = "jmh_results.json";
        }

        Options opt = new OptionsBuilder()
                .include(PipelineBenchmarks.class.getSimpleName())
                .param("dataset", datasetNames)
                .resultFormat(ResultFormatType.JSON)
                .result(outputPath)
                .build();

        new Runner(opt).run();
    }
}
