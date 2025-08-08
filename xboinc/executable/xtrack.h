// copyright ############################### #
// This file is part of the Xboinc Package.  #
// Copyright (c) CERN, 2025.                 #
// ######################################### #

// This file provides the necessary xsuite functions to main.c

#ifndef XB_XTRACK_HEADERS
#define XB_XTRACK_HEADERS

typedef struct ElementRefData_s * ElementRefData;

// We manually re-define ElementRefData_member_elements to a copycat
// MyElementRefData_member_elements to avoid the name clash and the big
// headache it would take to extract the static inline void* function coming
// from the original xtrack tracker code. 
void *MyElementRefData_member_elements(const ElementRefData obj, int64_t i0)
{
    int64_t offset = 0;
    offset += 16;
    offset += 16 + i0 * 16;
    offset += *(int64_t *)((char *)obj + offset);
    return (void *)((char *)obj + offset);
}

typedef struct ParticlesData_s *ParticlesData;
void track_line(int8_t*,ElementRefData,ParticlesData,int,int,int,int,int,int,int,double,int8_t*,int64_t,int8_t*);

typedef struct XbState_s * XbState;
int64_t XbState_get__i_turn(const XbState);
void XbState_set__i_turn(XbState,int64_t);
ParticlesData XbState_getp__particles(XbState);
int64_t XbState_get__particles__capacity(const XbState);
int64_t XbState_get__particles_state(const XbState,int64_t);
ElementRefData XbState_getp__monitors_metadata(XbState);

typedef struct XbInput_s * XbInput;
int64_t XbInput_get__version_xboinc_version(const XbInput);
int64_t XbInput_get_xb_state__version_xboinc_version(const XbInput);
int64_t XbInput_get_checkpoint_every(const XbInput);
ElementRefData XbInput_getp_line_metadata(XbInput);
int64_t XbInput_get_num_turns(const XbInput);
int64_t XbInput_get_num_elements(const XbInput);
int64_t XbInput_get_ele_start(const XbInput);
int64_t XbInput_get_ele_stop(const XbInput);
int64_t XbInput_get_num_monitors(const XbInput);
int64_t XbInput_get_idx_monitors(const XbInput, int64_t);
int64_t XbInput_get_size_monitors(const XbInput, int64_t);
XbState XbInput_getp_xb_state(XbInput);
int64_t XbInput_get_xb_state__xsize(const XbInput);

#endif /* XB_XTRACK_HEADERS */
