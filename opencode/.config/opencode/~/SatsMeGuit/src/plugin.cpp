#include <clap/clap.h>
#include <cstring>
#include <cmath>
#include <vector>
#include <array>

struct SatsMeGuit {
    clap_plugin_t plugin;
    const clap_host_t* host;
    
    // Parameters
    float input_gain = 0.0f;   // -12 to 12 dB
    float drive = 0.5f;        // 0 to 1
    float tone = 0.5f;         // 0 to 1
    float output_gain = 0.0f;  // -12 to 12 dB
    
    std::array<float, 2> last_sample = {0.0f, 0.0f}; // for simple filter
};

static const char* plugin_id = "com.satsmeguit.plugin";

static bool satsme_plugin_init(const clap_plugin_t* plugin) {
    return true;
}

static void satsme_plugin_destroy(const clap_plugin_t* plugin) {
    delete reinterpret_cast<SatsMeGuit*>(plugin->plugin_data);
}

static bool satsme_plugin_activate(const clap_plugin_t* plugin, double sample_rate, uint32_t min_frames_count, uint32_t max_frames_count) {
    return true;
}

static void satsme_plugin_deactivate(const clap_plugin_t* plugin) {}

static bool satsme_plugin_start_processing(const clap_plugin_t* plugin) { return true; }
static void satsme_plugin_stop_processing(const clap_plugin_t* plugin) {}

static void satsme_plugin_reset(const clap_plugin_t* plugin) {
    auto* self = reinterpret_cast<SatsMeGuit*>(plugin->plugin_data);
    self->last_sample[0] = 0.0f;
    self->last_sample[1] = 0.0f;
}

// Simple tube screamer style soft clip
static float soft_clip(float x, float drive) {
    float k = 1.0f + drive * 8.0f;
    return std::tanh(x * k) / k;
}

// Simple one-pole filter for tone
static float apply_tone(float x, float tone, float* state) {
    float cutoff = 0.1f + tone * 0.8f;
    *state = *state + cutoff * (x - *state);
    return *state;
}

static clap_process_status satsme_plugin_process(const clap_plugin_t* plugin, const clap_process_t* process) {
    auto* self = reinterpret_cast<SatsMeGuit*>(plugin->plugin_data);
    
    const float in_gain = std::pow(10.0f, self->input_gain / 20.0f);
    const float out_gain = std::pow(10.0f, self->output_gain / 20.0f);
    
    for (uint32_t i = 0; i < process->frames_count; ++i) {
        float in = process->audio_inputs[0].data32[0][i] * in_gain;
        
        // Apply drive/saturation
        float saturated = soft_clip(in, self->drive);
        
        // Simple tone (lowpass-ish)
        float toned = apply_tone(saturated, self->tone, &self->last_sample[0]);
        
        // Output
        float out = toned * out_gain * 0.8f; // safety
        
        process->audio_outputs[0].data32[0][i] = out;
        if (process->audio_outputs[0].channel_count > 1) {
            process->audio_outputs[0].data32[1][i] = out;
        }
    }
    
    return CLAP_PROCESS_CONTINUE;
}

// Parameter functions (stub for now)
static uint32_t satsme_get_param_count(const clap_plugin_t* plugin) { return 4; }

static bool satsme_get_param_info(const clap_plugin_t* plugin, uint32_t param_index, clap_param_info_t* param_info) {
    param_info->flags = CLAP_PARAM_IS_AUTOMATABLE;
    param_info->cookie = nullptr;
    
    switch (param_index) {
        case 0:
            std::strcpy(param_info->id, "input_gain");
            std::strcpy(param_info->name, "Input Gain");
            param_info->min_value = -12.0;
            param_info->max_value = 12.0;
            param_info->default_value = 0.0;
            break;
        case 1:
            std::strcpy(param_info->id, "drive");
            std::strcpy(param_info->name, "Drive");
            param_info->min_value = 0.0;
            param_info->max_value = 1.0;
            param_info->default_value = 0.5;
            break;
        case 2:
            std::strcpy(param_info->id, "tone");
            std::strcpy(param_info->name, "Tone");
            param_info->min_value = 0.0;
            param_info->max_value = 1.0;
            param_info->default_value = 0.5;
            break;
        case 3:
            std::strcpy(param_info->id, "output_gain");
            std::strcpy(param_info->name, "Output Gain");
            param_info->min_value = -12.0;
            param_info->max_value = 12.0;
            param_info->default_value = 0.0;
            break;
    }
    return true;
}

static bool satsme_get_param_value(const clap_plugin_t* plugin, clap_id param_id, double* value) {
    auto* self = reinterpret_cast<SatsMeGuit*>(plugin->plugin_data);
    if (std::strcmp(reinterpret_cast<const char*>(&param_id), "input_gain") == 0) *value = self->input_gain;
    else if (std::strcmp(reinterpret_cast<const char*>(&param_id), "drive") == 0) *value = self->drive;
    else if (std::strcmp(reinterpret_cast<const char*>(&param_id), "tone") == 0) *value = self->tone;
    else if (std::strcmp(reinterpret_cast<const char*>(&param_id), "output_gain") == 0) *value = self->output_gain;
    else return false;
    return true;
}

static bool satsme_params_set_value(const clap_plugin_t* plugin, clap_id param_id, double value) {
    auto* self = reinterpret_cast<SatsMeGuit*>(plugin->plugin_data);
    if (std::strcmp(reinterpret_cast<const char*>(&param_id), "input_gain") == 0) self->input_gain = value;
    else if (std::strcmp(reinterpret_cast<const char*>(&param_id), "drive") == 0) self->drive = value;
    else if (std::strcmp(reinterpret_cast<const char*>(&param_id), "tone") == 0) self->tone = value;
    else if (std::strcmp(reinterpret_cast<const char*>(&param_id), "output_gain") == 0) self->output_gain = value;
    else return false;
    return true;
}

static const clap_plugin_params_t plugin_params = {
    .count = satsme_get_param_count,
    .get_info = satsme_get_param_info,
    .get_value = satsme_get_param_value,
    .value_to_text = nullptr,
    .text_to_value = nullptr,
    .flush = nullptr,
};

static const void* satsme_plugin_get_extension(const clap_plugin_t* plugin, const char* id) {
    if (std::strcmp(id, CLAP_EXT_PARAMS) == 0) return &plugin_params;
    return nullptr;
}

static const clap_plugin_descriptor_t descriptor = {
    .clap_version = CLAP_VERSION,
    .id = "dev.satsmeguit.satsmeguit",
    .name = "SatsMeGuit",
    .vendor = "SatsMeGuit",
    .url = "https://github.com/user/satsmeguit",
    .manual_url = nullptr,
    .support_url = nullptr,
    .version = "1.0.0",
    .description = "Guitar saturation pedal with Tube Screamer style",
    .features = (const char*[]){CLAP_PLUGIN_FEATURE_AUDIO_EFFECT, CLAP_PLUGIN_FEATURE_DISTORTION, nullptr}
};

static const clap_plugin_t* satsme_plugin_create(const clap_host_t* host) {
    auto* self = new SatsMeGuit();
    self->plugin = {
        .desc = &descriptor,
        .plugin_data = self,
        .init = satsme_plugin_init,
        .destroy = satsme_plugin_destroy,
        .activate = satsme_plugin_activate,
        .deactivate = satsme_plugin_deactivate,
        .start_processing = satsme_plugin_start_processing,
        .stop_processing = satsme_plugin_stop_processing,
        .reset = satsme_plugin_reset,
        .process = satsme_plugin_process,
        .get_extension = satsme_plugin_get_extension,
        .on_main_thread = nullptr
    };
    self->host = host;
    return &self->plugin;
}

extern "C" const clap_plugin_entry_t clap_entry = {
    .clap_version = CLAP_VERSION,
    .init = nullptr,
    .deinit = nullptr,
    .get_factory = [](const char* factory_id) -> const void* {
        static const clap_plugin_factory_t factory = {
            .get_plugin_count = [](const clap_plugin_factory_t*) { return 1; },
            .get_plugin_descriptor = [](const clap_plugin_factory_t*, uint32_t index) { return index == 0 ? &descriptor : nullptr; },
            .create_plugin = [](const clap_plugin_factory_t*, const clap_host_t* host, const char* plugin_id) {
                if (std::strcmp(plugin_id, descriptor.id) == 0) return satsme_plugin_create(host);
                return (const clap_plugin_t*)nullptr;
            }
        };
        if (std::strcmp(factory_id, CLAP_PLUGIN_FACTORY_ID) == 0) return &factory;
        return nullptr;
    }
};
